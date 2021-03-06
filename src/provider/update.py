#!/usr/bin/env python3
# if the yaml import fails, run "pip install pyyaml"

import sys
import os
import yaml

out_all = ""
out_domains = ""
domains_dict = {}


def cleanstr(s):
    s = s.strip()
    s = s.replace("\n", " ")
    s = s.replace("\\", "\\\\")
    s = s.replace("\"", "\\\"")
    return s


def file2varname(f):
    f = f[f.rindex("/")+1:].replace(".md", "")
    f = f.replace(".", "_")
    f = f.replace("-", "_")
    return "P_" + f.upper()


def file2url(f):
    f = f[f.rindex("/")+1:].replace(".md", "")
    f = f.replace(".", "-")
    return "https://providers.delta.chat/" + f


def process_data(data, file):
    status = data.get("status", "")
    if status != "OK" and status != "PREPARATION" and status != "BROKEN":
        raise TypeError("bad status")

    comment = ""
    domains = ""
    if not "domains" in data:
        raise TypeError("no domains found")
    for domain in data["domains"]:
        domain = cleanstr(domain)
        if domain == "" or domain.count(".") < 1 or domain.lower() != domain:
            raise TypeError("bad domain: " + domain)

        global domains_dict
        if domains_dict.get(domain, False):
            raise TypeError("domain used twice: " + domain)
        domains_dict[domain] = True

        domains += "        (\"" + domain + "\", &*" + file2varname(file) + "),\n"
        comment += domain + ", "


    server = ""
    has_imap = False
    has_smtp = False
    if "server" in data:
        for s in data["server"]:
            hostname = cleanstr(s.get("hostname", ""))
            port = int(s.get("port", ""))
            if hostname == "" or hostname.count(".") < 1 or port <= 0:
                raise TypeError("bad hostname or port")

            protocol = s.get("type", "").upper()
            if protocol == "IMAP":
                has_imap = True
            elif protocol == "SMTP":
                has_smtp = True
            else:
                raise TypeError("bad protocol")

            socket = s.get("socket", "").upper()
            if socket != "STARTTLS" and socket != "SSL":
                raise TypeError("bad socket")

            username_pattern = s.get("username_pattern", "EMAIL").upper()
            if username_pattern != "EMAIL" and username_pattern != "EMAILLOCALPART":
                raise TypeError("bad username pattern")

            server += ("            Server { protocol: " + protocol + ", socket: " + socket + ", hostname: \""
            + hostname + "\", port: " + str(port) + ", username_pattern: " + username_pattern + " },\n")

    provider = ""
    before_login_hint = cleanstr(data.get("before_login_hint", ""))
    after_login_hint = cleanstr(data.get("after_login_hint", ""))
    if (not has_imap and not has_smtp) or (has_imap and has_smtp):
        provider += "    static ref " + file2varname(file) + ": Provider = Provider {\n"
        provider += "        status: Status::" + status + ",\n"
        provider += "        before_login_hint: \"" + before_login_hint + "\",\n"
        provider += "        after_login_hint: \"" + after_login_hint + "\",\n"
        provider += "        overview_page: \"" + file2url(file) + "\",\n"
        provider += "        server: vec![\n" + server + "        ],\n"
        provider += "    };\n\n"
    else:
        raise TypeError("SMTP and IMAP must be specified together or left out both")

    if status != "OK" and before_login_hint == "":
        raise TypeError("status PREPARATION or BROKEN requires before_login_hint: " + file)

    # finally, add the provider
    global out_all, out_domains
    out_all += "    // " + file[file.rindex("/")+1:] + ": " + comment.strip(", ") + "\n"
    if status == "OK" and before_login_hint == "" and after_login_hint == "" and server == "":
        out_all += "    // - skipping provider with status OK and no special things to do\n\n"
    else:
        out_all += provider
        out_domains += domains


def process_file(file):
    print("processing file: " + file, file=sys.stderr)
    with open(file) as f:
        # load_all() loads "---"-separated yamls -
        # by coincidence, this is also the frontmatter separator :)
        data = next(yaml.load_all(f, Loader=yaml.SafeLoader))
        process_data(data, file)


def process_dir(dir):
    print("processing directory: " + dir, file=sys.stderr)
    files = [f for f in os.listdir(dir) if f.endswith(".md")]
    files.sort()
    for f in files:
        process_file(os.path.join(dir, f))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: update.py DIR_WITH_MD_FILES > data.rs")

    out_all = ("// file generated by src/provider/update.py\n\n"
    "use crate::provider::Protocol::*;\n"
    "use crate::provider::Socket::*;\n"
    "use crate::provider::UsernamePattern::*;\n"
    "use crate::provider::*;\n"
    "use std::collections::HashMap;\n\n"
    "lazy_static::lazy_static! {\n\n")

    process_dir(sys.argv[1])

    out_all += "    pub static ref PROVIDER_DATA: HashMap<&'static str, &'static Provider> = [\n"
    out_all += out_domains;
    out_all += "    ].iter().copied().collect();\n}"

    print(out_all)
