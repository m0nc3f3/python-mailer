# python Mailer

A **simple Python SMTP email sender** made by Moncef Fennan.

## Features
- Send emails to multiple recipients from a list
- Attach multiple files
- Automatically looks up MX records per domain (or use your own SMTP server)
- Securely store credentials in your system keychain
- CLI-based using `argparse`
- Works with plain text or message files

## Installation
```bash
git clone https://github.com/m0nc3f3/python-mailer.git
cd python-mailer
pip install -r requirements.txt
