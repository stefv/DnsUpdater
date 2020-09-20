#!/usr/bin/python3

# Copyright 2020 https://github.com/stefv
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# If you need to install modules, just use: pip3 install <module_name>
# The original web site of this script is: https://github.com/stefv/DnsUpdater

# Version history:
# v1.0 : first version

import sys
import socket
import pathlib
import configparser
import requests
import json

CONFIG_FILE = "dns_updater.ini"

# This class will update the A record of your domain hosted by Gandi.net. To
# use it, you need to have an API key. Follow the instructions here:
# https://docs.gandi.net/en/domain_names/advanced_users/api.html
# You need also a dynamic domain name hosted by a provider like No-ip,
# DynDNS, ChangeIP, ... This domain name will be updated by your internet box
# and this script will find the IP address with the dynamic domain name.
# Just use crontab to call this script every 5 minutes. When the IP of your box
# will change, this script will update the A record of the DNS.
# When you start for the first time this script, a gandi.ini file is created
# with default settings. Go to the https://github.com/stefv/DnsUpdater web
# site to have a better description of the options.


class DNSUpdater:

    # Last IP address
    __ip = None

    # The API key of Gandi
    __apikey = None

    # The dynamic DNS host
    __ddnsHostname = None

    # URL for the service to manage the records
    __liveDNSRecordUrl = None

    # Hosts to update.
    __hosts = None

    # Initialize the configuration file.
    def __init__(self):
        self.__createConfigTemplateIfDoesntExist()
        self.__readConfig()
        self.__checkConfig()

    # Update the A record in the Gandi DNS with the current IP address of the
    # internet box.
    def updateARecords(self):
        previous_ip_address = self.__getPreviousIPAddress()
        current_ip_address = self.__getCurrentIpAddress()
        print(f"Current IP address:  {current_ip_address}")
        if (previous_ip_address != current_ip_address):
            print(f"Previous IP address: {previous_ip_address}")
            self.__saveCurrentIPAddress()
            hosts = self.__hosts.split(",")
            for host in hosts:
                self.__updateARecord(host, current_ip_address)
            print(f"IP address updated on Gandi.")
        else:
            print(f"The IP address didn't change.")

    # Update the A record of the given host.
    # host : the host to update.
    def __updateARecord(self, host, current_ip_address):
        url = self.__liveDNSRecordUrl.replace("{host}", host)
        data = {"rrset_values": [ current_ip_address ]}
        headers = {"Content-type": "application/json",
                   "Authorization": f"ApiKey {self.__apikey}"}
        request = requests.put(url, data=json.dumps(data), headers=headers)
        if (request.status_code == 201):
            sys.stdout.write(f"IP address for {host} updated.\n")
        else:
            sys.stderr.write(f"Can't update the IP address for {host}.\n")

    # Create the config file with the minimal settings if is doesn't exists to
    # help the user to configure the tool.
    def __createConfigTemplateIfDoesntExist(self):
        settings = pathlib.Path(CONFIG_FILE)
        if not settings.exists():
            # The ip is empty because to initialize it we need the
            # ddnsHostname set. Only the user can set the ddnsHostname value.
            settings = open(CONFIG_FILE, "w")
            settings.write("[General]\n")
            settings.write("#apikey=YOUR_GANDI_API_KEY\n")
            settings.write("#ddnsHostname=DYNAMIC_DNS_HOST\n")
            settings.write("ip=\n\n")
            settings.write("[Services]\n")
            settings.write(
                "livednsRecordUrl=https://api.gandi.net/v5/livedns/domains/{host}/records/%%40/A\n")
            settings.write("#hosts=YOUR_HOSTS_SEPARATED_BY_COMMA\n")
            settings.close()

    # Read the configuration from the ini file to set the Gandi's class fields.
    def __readConfig(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(CONFIG_FILE)
        if len(dataset) > 0:
            self.__ip = parser.get("General", "ip", fallback=None)
            self.__apikey = parser.get("General", "apikey", fallback=None)
            self.__ddnsHostname = parser.get(
                "General", "ddnsHostname", fallback=None)
            self.__liveDNSRecordUrl = parser.get(
                "Services", "livednsRecordUrl", fallback=None)
            self.__hosts = parser.get("Services", "hosts", fallback=None)
        else:
            sys.stderr.write("Can't find the configuration file.\n")
            sys.exit(1)

    # Check if the mandatory settings are set. If not, quit the script with an
    # error.
    def __checkConfig(self):
        settings = pathlib.Path(CONFIG_FILE)
        # We must check the IP at the end to be sure the apikey and the
        # ddnsHostname are set.
        if not settings.exists():
            sys.stderr.write("Can't find the configuration file.\n")
            sys.exit(1)
        if (self.__apikey == None):
            sys.stderr.write("Empty setting for General/apikey.\n")
            sys.exit(1)
        if (self.__ddnsHostname == None):
            sys.stderr.write("Empty setting for General/ddnsHostname.\n")
            sys.exit(1)
        if (self.__liveDNSRecordUrl == None):
            sys.stderr.write("Empty setting for General/liveDNSRecordUrl.\n")
            sys.exit(1)
        if (self.__hosts == None):
            sys.stderr.write("Empty setting for General/hosts.\n")
            sys.exit(1)
        if (self.__ip == None or self.__ip == ""):
            self.__saveCurrentIPAddress()

    # Retrieve the previous IP address from the data file
    def __getPreviousIPAddress(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(CONFIG_FILE)
        if len(dataset) > 0:
            ip_address = parser.get("General", "ip", fallback=None)
            if (ip_address == None or ip_address == ""):
                self.__saveCurrentIPAddress()
                ip_address = self.__ip
        else:
            ip_address = self.__getCurrentIpAddress()
            parser.set("General", "ip", ip_address)
        return ip_address

    # Save the current IP address to the data file
    def __saveCurrentIPAddress(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(CONFIG_FILE)
        if len(dataset) > 0:
            self.__ip = self.__getCurrentIpAddress()
            parser.set("General", "ip", self.__ip)
            with open(CONFIG_FILE, "w") as configFile:
                parser.write(configFile)

    # Retrieve the current IP address of the server (using a dynamic IP address
    # provider: ie. no-ip)
    def __getCurrentIpAddress(self):
        ip_address = socket.gethostbyname(self.__ddnsHostname)
        return ip_address


print("===================================================")
print("= DNS Updater                                     =")
print("= Script to update the IP address of the A record =")
print("===================================================\n")

# Update the IP address of the host in the DNS of Gandi
dnsUpdater = DNSUpdater()
dnsUpdater.updateARecords()

print("Bye !\n\n")
