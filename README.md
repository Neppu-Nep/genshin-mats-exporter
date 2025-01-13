# Genshin Materials GOOD Exporter
Export Genshin materials in `GOOD` format using the Hoyolab's enhancement progression calculator.

## Requirements
- Python 3.10 or higher

## Installation
`pip install -r requirements.txt`

## How to get the Hoyolab cookies
1. Go to [Hoyolab](https://www.hoyolab.com/)
2. Log in.
3. Press `F12` to open the developer tools.
4. Go to the `Application` tab.
5. Go to `Cookies` > `https://www.hoyolab.com`
6. Copy the `ltoken_v2` and `ltuid_v2` values.
7. Format the values as `ltoken_v2=your_ltoken_v2;ltuid_v2=your_ltuid_v2;` and put it in the `COOKIES` field in the `.env` file.
8. Put your UID in the `UID` field in the `.env` file.
9. Save the file.

## Usage
1. Copy `.env.example` to `.env` and fill in the required fields
2. Run `python main.py`

## Known Issues
1. There's a delay of about 15-30 mins between obtaining the item in-game and being updated on Hoyolab's enhancement progression calculator.

2. The script currently doesn't export the following materials. (Blame Hoyoverse for not including them in the enhancement progression calculator)
    - Adventurer's Experience
    - Wanderer's Advice
    - Fine Enhancement Ore
    - Enhancement Ore

## FAQ

Why should I use this?
- You don't need to.
- This is just my personal project for updating my materials tracker since I'm too lazy to use scanners and haven't found any website that automatically updates the materials for me.
- https://seelie.me/ tries to do the same way but their calculation gives false results.
