import argparse
import smtplib
import getpass
import time
import random
import keyring
import pyfiglet
from pathlib import Path
from email.message import EmailMessage
from colorama import Fore, init

init(autoreset=True)

# ---------- BANNER ----------
def show_banner():
    banner = pyfiglet.figlet_format("0x4rt1st", font="slant")
    print(Fore.CYAN + banner)
    print(Fore.YELLOW + "  Made by Moncef Fennan")
    print(Fore.WHITE + "  Simple SMTP Email Sender")
    print(Fore.RED + "  ----------------------------------------\n")

show_banner()

# ---------- ARGUMENTS ----------
parser = argparse.ArgumentParser(description="Simple email sender")
parser.add_argument("-l", "--list",        help="file containing email list")
parser.add_argument("-s", "--subject",     help="email subject")
parser.add_argument("-m", "--message",     help="message text or file")
parser.add_argument("-a", "--attach",      nargs="*", help="attachments")
parser.add_argument("--setup",             action="store_true", help="store credentials")
parser.add_argument("--smtp-server",       default="smtp.gmail.com", help="SMTP server address (default: smtp.gmail.com)")
parser.add_argument("--smtp-port",         default=587, type=int, help="SMTP server port (default: 587)")
args = parser.parse_args()

# ---------- SETUP ----------
if args.setup:
    email    = input("Email: ").strip()        # add .strip()
    password = getpass.getpass("Password: ").strip()  # add .strip()
    keyring.set_password("mailer_script", "email", email)
    keyring.set_password("mailer_script", email, password)
    print(Fore.GREEN + "Credentials saved securely in system keychain.")
    exit()

# ---------- LOAD CREDENTIALS ----------
sender = keyring.get_password("mailer_script", "email")
if not sender:
    print(Fore.RED + "No credentials found. Run with --setup first.")
    exit(1)

password = keyring.get_password("mailer_script", sender)
if not password:
    print(Fore.RED + "No password found. Run with --setup first.")
    exit(1)

# ---------- VALIDATE ARGS ----------
if not args.list or not args.subject or not args.message:
    parser.error("--list, --subject, and --message are all required")

# ---------- LOAD EMAIL LIST ----------
email_file = Path(args.list)
if not email_file.exists():
    print(Fore.RED + f"Error: email list file '{email_file}' not found.")
    exit(1)

with open(email_file) as f:
    recipients = [line.strip() for line in f if line.strip()]

if not recipients:
    print(Fore.RED + "Error: email list is empty.")
    exit(1)

# ---------- LOAD MESSAGE ----------
message_path = Path(args.message)
if message_path.exists():
    with open(message_path) as f:
        message_text = f.read()
else:
    message_text = args.message

# ---------- LOAD ATTACHMENTS ----------
attachments = []
if args.attach:
    for file in args.attach:
        file_path = Path(file)
        if not file_path.exists():
            print(Fore.YELLOW + f"Warning: attachment '{file}' not found, skipping.")
            continue
        with open(file_path, "rb") as f:
            attachments.append((file_path.name, f.read()))

# ---------- CONNECT SMTP ----------
print(Fore.CYAN + "Connecting to SMTP server...")
try:
    server = smtplib.SMTP(args.smtp_server, args.smtp_port, timeout=30)
    server.starttls()
    server.login(sender, password)
    print(Fore.GREEN + "Connected.\n")
except Exception as e:
    print(Fore.RED + f"Failed to connect/login: {e}")
    exit(1)

# ---------- SEND EMAILS ----------
total      = len(recipients)
sent_count = 0
failed     = []

if total <= 50:
    delay_range = (1, 3)
elif total <= 200:
    delay_range = (2, 5)
else:
    delay_range = (3, 8)

for i, r in enumerate(recipients, 1):
    msg = EmailMessage()
    msg["From"]    = sender
    msg["To"]      = r
    msg["Subject"] = args.subject
    msg.set_content(message_text)

    for filename, data in attachments:
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=filename
        )

    try:
        try:
            server.noop()
        except smtplib.SMTPServerDisconnected:
            print(Fore.YELLOW + "Connection lost, reconnecting...")
            server = smtplib.SMTP(args.smtp_server, args.smtp_port, timeout=30)
            server.starttls()
            server.login(sender, password)

        server.send_message(msg)
        sent_count += 1
        print(Fore.GREEN + f"  [{i}/{total}] Sent -> {r}")
    except Exception as e:
        failed.append(r)
        print(Fore.RED + f"  [{i}/{total}] Failed -> {r}: {e}")

    if i < total:
        time.sleep(random.uniform(*delay_range))

server.quit()

# ---------- SUMMARY ----------
print(Fore.CYAN + "\n----------------------------------------")
print(Fore.GREEN + f"  Sent:   {sent_count}/{total}")
if failed:
    print(Fore.RED + f"  Failed: {len(failed)}")
    print(Fore.RED + "  Failed recipients:")
    for r in failed:
        print(Fore.RED + f"    - {r}")
else:
    print(Fore.GREEN + "  All emails sent successfully.")
print(Fore.CYAN + "----------------------------------------\n")
