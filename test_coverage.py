# generate_keys() -> list


from generator import generate_keys
import argparse, os, json, collections, logging, time

#TODO: Add description
description = '''Analyze coverage of frequency based character combinations within a given text file:
\tpython3 test_coverage.py rockyou.txt -i frequency_en.json
Compare coverage of frequency based character with all 2-character combinations:
\tpython3 test_coverage.py rockyou.txt -i frequency_en.json -c'''

# Initialize argument parsing
class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass
parser = argparse.ArgumentParser(
    epilog=description,
    formatter_class=CustomFormatter,
    description="Tests efficiency of frequency based character combinations.")

general_group = parser.add_argument_group("GENERAL")
parser.add_argument("input", type = str, help="Contains the text to analyze (e.g. rockyou.txt). This represents the values a user types into the input field.")
parser.add_argument("-i", "--input-file", type = str, required=True, default="freq_en.json", help="Input JSON file that contains histogram of frequent character combinations (can be generated using frequency_analyzer.py)")
parser.add_argument("-n", "--num-selectors", type = int, default=5000, help="Maximum number of selectors to generate (will get overwritten if comparision is enabled)")

general_group = parser.add_argument_group("FILTER")
parser.add_argument("--start", default=0x20, type = int, help="Ignore characters below this value (e.g. 0x20 for space)")
parser.add_argument("--end", default=0x7e, type = int, help="Ignore characters above this value (e.g. 0x7e for tilde)")
parser.add_argument("-e", "--encoding", default="utf-8", type = str, help="Encoding to use for reading the file")
parser.add_argument("-c", "--compare", action="store_true", help="Compares coverage of all 2-character combinations over statistical approach")
parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")

args = parser.parse_args()

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(args.verbose and logging.DEBUG or logging.INFO)
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Check if file (to analyze) exists
if not os.path.isfile(args.input):
    logger.error(f"File {args.input} does not exist")
    exit(1)

# Check if file (JSON frequency file) exists
if not os.path.isfile(args.input_file):
    logger.error(f"File {args.input_file} does not exist")
    exit(1)


# Read file (to analyze)
lines = []
with open(args.input, "r", encoding=args.encoding, errors="ignore") as f:
    # Remove empty lines and lines containing characters outside the range
    for line in f.read().splitlines():
        if line and not any(ord(c) < args.start or ord(c) > args.end for c in line):
            lines.append(line)
    logger.debug(f"Read {len(lines):,} lines from '{args.input}'")

# Generate all 2-character combinations
t_combs = []
if args.compare:
    for i in range(args.start, args.end + 1):
        for j in range(args.start, args.end + 1):
            t_combs.append(chr(i) + chr(j))

    assert len(t_combs) > 0, "Failed to generate 2-character combinations (probably due to invalid start and end values)"
    logger.debug(f"Generated {len(t_combs):,} 2-character combinations")

    # Overwrite maximum number of selectors
    args.num_selectors = len(t_combs)

# Load JSON frequency file
s_combs = None
with open(args.input_file, "r") as f:
    s_combs = json.load(f)
assert s_combs, f"Failed to read JSON file {args.input_file}"
s_combs = generate_keys(s_combs, args.num_selectors, logger=logger)
logger.debug(f"Generated {len(s_combs):,} n-character combinations")


# TODO: This function is excessively slow
def test_exfiltrate(combinations: list, input_value: list) -> bool:
    '''
    Tests if a given input value could get exfiltrated using the given combinations as CSS selectors.
    '''
    exfiltrated = ""
    for cur_val in input_value:
        # this simluates a keyup event (the user types a character)
        # the pressed key is then always appended to the attribute value by e.g. a JavaScript event listener

        # check if the attribute value ends with any of the combinations
        # if it does, remove the combination from the list
        cur_val_len = len(cur_val)
        f_cur = cur_val[-1] 
        for comb in combinations:
            # instead of using the .endswith() method, we implement it manually to improve performance
            # if the last character of the combination is not equal to the last character of the attribute value, skip
            if f_cur != comb[-1]: continue
            # if the combination is longer than the attribute value, skip
            if len(comb) > cur_val_len: continue
            # if the combination does not end with the attribute value, skip
            idx = cur_val_len - len(comb)
            if cur_val[idx:] != comb: continue

            # abc + d -> abcd
            if len(comb) == 1:
                exfiltrated += comb
            # abc + bcd -> abcd
            # abc + def -> abcdef
            else:
                # Check how many characters are common
                common = 0
                for i in range(min(len(comb), len(exfiltrated)), 0, -1):
                    if exfiltrated.endswith(comb[:i]):
                        common = i
                        break
                # Add the remaining characters
                exfiltrated += comb[common:]
            combinations.remove(comb)
            break
    # check if the exfiltrated value is equal to the input value
    #print(f"Exfiltrated: {exfiltrated}, Input: {input_value}")
    return exfiltrated == input_value[-1]

# Keep track of all values that could not get exfiltrated
s_comb_fails, t_comb_fails = [], []
ctr, total = 0, len(lines)

for line in lines:
    # Precalculate line to avoid redundant calculations
    line = [line[:i] for i in range(1, len(line) + 1)]
    # Test single character combinations
    if not test_exfiltrate(s_combs, line):
        s_comb_fails.append(line)
    # Test all 2-character combinations
    if args.compare and not test_exfiltrate(t_combs, line):
        t_comb_fails.append(line)
    ctr += 1
    if ctr % 100 == 0:
        logger.debug(f"Progress: {ctr / total * 100:.1f}%")

print(f"\nResults for {args.input_file} (total: {len(lines):,} lines)")

# Print results for both statistical and 2-character combinations (#passed (percentage), #failed (percentage))
print(f"Statistical approach:")
print(f"Passed: {len(lines) - len(s_comb_fails)} ({(len(lines) - len(s_comb_fails)) / len(lines) * 100:.2f}%)")
print(f"Failed: {len(s_comb_fails)} ({len(s_comb_fails) / len(lines) * 100:.2f}%)")

if args.compare:
    print(f"\nAll 2-character combinations:")
    print(f"Passed: {len(lines) - len(t_comb_fails)} ({(len(lines) - len(t_comb_fails)) / len(lines) * 100:.2f}%)")
    print(f"Failed: {len(t_comb_fails)} ({len(t_comb_fails) / len(lines) * 100:.2f}%)")
