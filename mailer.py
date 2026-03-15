import keyring
import pyfiglet
import argparse
import smtplib
import getpass
import time
import random
import dns.resolver
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

# ---------- MX LOOKUP ----------
def get_mx(domain):
    '''this function looks up the MX record for a given domain.
    MX records tell us which mail server handles emails for that domain.
     gmail.com -> aspmx.l.google.com
                 outlook.com -> outlook-com.olc.protection.outlook.com
    '''
    try:
        records = dns.resolver.resolve(domain, "MX")
        
        mx = sorted(records, key=lambda r: r.preference)[0]
        return str(mx.exchange).rstrip(".")  
    except Exception:
        return None

# ---------- ARGUMENTS ----------
parser = argparse.ArgumentParser(description="Simple email sender")
parser.add_argument("-l", "--list",    help="file containing email list")
parser.add_argument("-s", "--subject", help="email subject")
parser.add_argument("-m", "--message", help="message text or file")
parser.add_argument("-a", "--attach",  nargs="*", help="attachments")
parser.add_argument("--setup",         action="store_true", help="store credentials")
parser.add_argument("--smtp-server",   default=None, help="force a specific SMTP server (overrides MX lookup)")
parser.add_argument("--smtp-port",     default=587, type=int, help="SMTP server port (default: 587)")
args = parser.parse_args()

# ---------- SETUP ----------
if args.setup:
    email    = input("Email: ")
    password = getpass.getpass("Password: ")
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

# ---------- PRE-RESOLVE MX RECORDS ----------

domain_mx = {}
print(Fore.CYAN + "Resolving mail servers...")

for r in recipients:
    if "@" not in r:
        print(Fore.RED + f"  Invalid email skipped: {r}")
        continue
    domain = r.split("@")[1].lower()
    if domain not in domain_mx:
        if args.smtp_server:
            # user forced a specific server, skip MX lookup entirely
            domain_mx[domain] = args.smtp_server
            print(Fore.WHITE + f"  {domain} -> {args.smtp_server} (forced)")
        else:
            mx = get_mx(domain)
            if mx:
                domain_mx[domain] = mx
                print(Fore.GREEN + f"  {domain} -> {mx}")
            else:
                domain_mx[domain] = None
                print(Fore.RED + f"  {domain} -> MX lookup failed, will skip recipients")

print()

# ---------- GROUP RECIPIENTS BY SMTP SERVER ----------

server_groups = {}
skipped = []

for r in recipients:
    if "@" not in r:
        skipped.append(r)
        continue
    domain = r.split("@")[1].lower()
    mx = domain_mx.get(domain)
    if not mx:
        skipped.append(r)
        continue
    if mx not in server_groups:
        server_groups[mx] = []
    server_groups[mx].append(r)

# ---------- SEND EMAILS ----------
total      = len(recipients)
sent_count = 0
failed     = list(skipped) 

if total <= 50:
    delay_range = (1, 3)
elif total <= 200:
    delay_range = (2, 5)
else:
    delay_range = (3, 8)

# loop over each unique mail server and send to its recipients in one session
for smtp_host, group in server_groups.items():
    print(Fore.CYAN + f"Connecting to {smtp_host}:{args.smtp_port}...")
    try:
        server = smtplib.SMTP(smtp_host, args.smtp_port, timeout=30)
        server.starttls()
        server.login(sender, password)
        print(Fore.GREEN + f"Connected to {smtp_host}\n")
    except Exception as e:
        print(Fore.RED + f"Failed to connect to {smtp_host}: {e}")
        failed.extend(group)
        continue  

    for i, r in enumerate(group, 1):
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
                server = smtplib.SMTP(smtp_host, args.smtp_port, timeout=30)
                server.starttls()
                server.login(sender, password)

            server.send_message(msg)
            sent_count += 1
            print(Fore.GREEN + f"  [{sent_count}/{total}] Sent -> {r}")
        except Exception as e:
            failed.append(r)
            print(Fore.RED + f"  [!/{total}] Failed -> {r}: {e}")

        if i < len(group):
            time.sleep(random.uniform(*delay_range))

    server.quit()
    print()

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
