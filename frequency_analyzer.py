import argparse, os, json, collections, logging, time

description = '''Analyze frequency of characters in a text file:
\tpython3 frequency_analyzer.py -i rockyou.txt
Analyze frequency of characters in a text file and save the results to a file:
\tpython3 frequency_analyzer.py -i rockyou.txt -o frequency_en.json
Analyze 1, 2 and 3 character combinations in a text file:
\tpython3 frequency_analyzer.py -i rockyou.txt -s 1,2,3'''

# Initialize argument parsing
parser = argparse.ArgumentParser(
    epilog=description,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description="Frequency analyzer of character combinations in a text file")

general_group = parser.add_argument_group("GENERAL")
parser.add_argument("-i", "--input-file", type = str, required=True, help="File to analyze (line by line)")
parser.add_argument("-o", "--output-file", type = str, help="File to save the results to in JSON format")

general_group = parser.add_argument_group("FILTER")
parser.add_argument("--start", default=0x20, type = int, help="Ignore characters below this value (e.g. 0x20 for space)")
parser.add_argument("--end", default=0x7e, type = int, help="Ignore characters above this value (e.g. 0x7e for tilde)")
parser.add_argument("-e", "--encoding", default="utf-8", type = str, help="Endcoding to use for reading the file")
parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")

general_group = parser.add_argument_group("PARAMS")
parser.add_argument("-s", "--sizes", default="1,2,3", type = str, help="Comma-separated list of sizes to analyze (e.g. 1,2,3 will analyze 1, 2 and 3 character combinations)")

args = parser.parse_args()

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(args.verbose and logging.DEBUG or logging.INFO)
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


# Get sizes to analyze
sizes = list(map(int, args.sizes.split(",")))
# Sizes must contain at least one element and '1' must be present
assert sizes, "At least one size must be specified"
# sort and remove duplicates
sizes = sorted(set(sizes))
if not 1 in sizes:
    sizes.insert(0, 1)
    logger.warning("Size '1' not present in the list, adding it")

# Check if file exists
if not os.path.isfile(args.input_file):
    logger.error(f"File {args.input_file} does not exist")
    exit(1)

# Read file
lines = []
with open(args.input_file, "r", encoding=args.encoding, errors="ignore") as f:
    # Remove empty lines and lines containing characters outside the range
    for line in f.read().splitlines():
        if not any(ord(c) < args.start or ord(c) > args.end for c in line):
            lines.append(line)
    logger.debug(f"Read {len(lines):,} lines from '{args.input_file}'")

# Create all collection for each size
collections = {size: collections.Counter() for size in sizes}

for size in sizes:
    collection = collections[size]
    logger.debug(f"Analyzing {size}-character combinations...")
    ctr, total, start_time = 0, len(lines), time.time()
    if size > 1:
        for line in lines:
            ctr += 1
            collections[size].update([line[i:i+size] for i in range(len(line)-size+1)])
            if ctr % 1_000_000 == 0:
                logger.debug(f"{size}-char progress: {ctr / total * 100:.1f}%")
    # Threat 1-character combinations differently as there is no need to split the line
    else:
        for line in lines:
            ctr += 1
            collections[size].update(line)
            if ctr % 1_000_000 == 0:
                logger.debug(f"{size}-char progress: {ctr / total * 100:.1f}%")
    logger.debug(f"Analyzed {ctr:,} lines in {time.time() - start_time:.2f} seconds")

# Print collections
for size, collection in collections.items():
    logger.info(f"Top 100 {size}-character combinations:")
    logger.info(collection.most_common(100))

# Save to file
if args.output_file:
    with open(args.output_file, "w") as f:
        json.dump(collections, f, indent=4)
    logger.info(f"Saved results to {args.output_file}")