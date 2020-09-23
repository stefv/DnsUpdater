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

import os
import sys
import socket
import pathlib
import configparser
import requests
import json
import datetime
import logging
import logging.handlers

VERSION = "1"
CONFIG_FILE = "dns_updater.ini"

GENERAL_SECTION = "General"
LOGGING_SECTION = "Logging"
EMAIL_SECTION = "Email"
GANDI_SECTION = "Gandi"

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


class DNSUpdater(object):

    # The logger
    __logger = None

    # Script version
    __version = None

    # Last IP address
    __ip = None

    # The API key of Gandi
    __apikey = None

    # The dynamic DNS host
    __ddnsHostname = None

    # URL for the service to manage the records
    __liveDNSRecordUrl = None

    # Hosts to update
    __hosts = None

    # Initialize the configuration file.
    def __init__(self):
        self.__createConfigTemplateIfDoesntExist()
        self.__logger = Logger()
        self.__readConfig()
        self.__checkConfig()

    # Update the A record in the Gandi DNS with the current IP address of the
    # internet box.
    def updateARecords(self):
        previous_ip_address = self.__getPreviousIPAddress()
        current_ip_address = self.__getCurrentIpAddress()
        self.__logger.info(f"Current IP address:  {current_ip_address}")
        if (previous_ip_address != current_ip_address):
            self.__logger.info(f"Previous IP address: {previous_ip_address}")
            self.__saveCurrentIPAddress()
            hosts = self.__hosts.split(",")
            for host in hosts:
                self.__updateARecord(host.strip(), current_ip_address)
            self.__logger.info(f"IP address updated on Gandi.")
        else:
            self.__logger.info(f"The IP address didn't change.")

    # Retrieve the path to the ini file.
    def __getIniFilePath(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, CONFIG_FILE)
        return filename

    # Update the A record of the given host.
    # host : the host to update.
    # current_ip_address : current IP address to update.
    def __updateARecord(self, host, current_ip_address):
        url = self.__liveDNSRecordUrl.replace("{host}", host)
        data = {"rrset_values": [current_ip_address]}
        headers = {"Content-type": "application/json", "Authorization": f"ApiKey {self.__apikey}"}
        request = requests.put(url, data=json.dumps(data), headers=headers)
        if (request.status_code == 201):
            self.__logger.info(f"IP address for {host} updated.")
        else:
            self.__logger.error(f"Can't update the IP address for {host}.")

    # Create the config file with the minimal settings if is doesn't exists to
    # help the user to configure the tool.
    def __createConfigTemplateIfDoesntExist(self):
        settings = pathlib.Path(self.__getIniFilePath())
        if not settings.exists():
            # The ip is empty because to initialize it we need the
            # ddnsHostname set. Only the user can set the ddnsHostname value.
            settings = open(self.__getIniFilePath(), "w")
            settings.write(f"[{GENERAL_SECTION}]\n")
            settings.write("version=1\n")
            settings.write("#ddnsHostname=DYNAMIC_DNS_HOST\n")
            settings.write("ip=\n\n")
            settings.write(f"[{LOGGING_SECTION}]\n")
            settings.write("logFile=dns_updater.log\n")
            settings.write("logFileWhen=midnight\n")
            settings.write("logFileInterval=3600\n")
            settings.write("logFileBackupCount=10\n\n")
            # settings.write(f"[{EMAIL_SECTION}]\n")
            # settings.write("#emailAddresses=EMAIL_ADDRESSES\n")
            # settings.write("emailSubject=\"[DNSUpdater] Update report\"\n\n")
            settings.write(f"[{GANDI_SECTION}]\n")
            settings.write("#apikey=YOUR_GANDI_API_KEY\n")
            settings.write("livednsRecordUrl=https://api.gandi.net/v5/livedns/domains/{host}/records/%%40/A\n")
            settings.write("#hosts=YOUR_HOSTS_SEPARATED_BY_COMMA\n")
            settings.close()

            sys.stderr.write("Creating a template file for the settings.\n")
            sys.exit(1)

    # Read the configuration from the ini file to set the Gandi's class fields.
    def __readConfig(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(self.__getIniFilePath())
        if len(dataset) > 0:
            self.__version = parser.get(
                GENERAL_SECTION, "version", fallback=None)
            if (self.__version != VERSION):
                self.__logger.info(f"The configuration file is for version {self.__version} but the script is for version {VERSION}. " +
                                   f"Please, upgrade your configuration file to respect the new format. If you don't know this format, just rename your old ini file and start again\nthe script.")
                sys.exit(1)
            self.__ip = parser.get(GENERAL_SECTION, "ip", fallback=None)
            self.__ddnsHostname = parser.get(GENERAL_SECTION, "ddnsHostname", fallback=None)
            self.__apikey = parser.get(GANDI_SECTION, "apikey", fallback=None)
            self.__liveDNSRecordUrl = parser.get(GANDI_SECTION, "livednsRecordUrl", fallback=None)
            self.__hosts = parser.get(GANDI_SECTION, "hosts", fallback=None)
        else:
            self.__logger.error("Can't find the configuration file.\n")
            sys.exit(1)

    # Check if the mandatory settings are set. If not, quit the script with an
    # error.
    def __checkConfig(self):
        settings = pathlib.Path(self.__getIniFilePath())
        # We must check the IP at the end to be sure the apikey and the
        # ddnsHostname are set.
        if not settings.exists():
            self.__logger.error("Can't find the configuration file.\n")
            sys.exit(1)
        if (self.__apikey == None):
            self.__logger.error("Empty setting for General/apikey.\n")
            sys.exit(1)
        if (self.__ddnsHostname == None):
            self.__logger.error("Empty setting for General/ddnsHostname.\n")
            sys.exit(1)
        if (self.__liveDNSRecordUrl == None):
            self.__logger.error("Empty setting for General/liveDNSRecordUrl.\n")
            sys.exit(1)
        if (self.__hosts == None):
            self.__logger.error("Empty setting for General/hosts.\n")
            sys.exit(1)
        if (self.__ip == None or self.__ip == ""):
            self.__saveCurrentIPAddress()

    # Retrieve the previous IP address from the data file
    def __getPreviousIPAddress(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(self.__getIniFilePath())
        if len(dataset) > 0:
            ip_address = parser.get(GENERAL_SECTION, "ip", fallback=None)
            if (ip_address == None or ip_address == ""):
                self.__saveCurrentIPAddress()
                ip_address = self.__ip
        else:
            ip_address = self.__getCurrentIpAddress()
            parser.set(GENERAL_SECTION, "ip", ip_address)
        return ip_address

    # Save the current IP address to the data file
    def __saveCurrentIPAddress(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(self.__getIniFilePath())
        if len(dataset) > 0:
            self.__ip = self.__getCurrentIpAddress()
            parser.set(GENERAL_SECTION, "ip", self.__ip)
            with open(self.__getIniFilePath(), "w") as configFile:
                parser.write(configFile)

    # Retrieve the current IP address of the server (using a dynamic IP address
    # provider: ie. no-ip)
    def __getCurrentIpAddress(self):
        ip_address = socket.gethostbyname(self.__ddnsHostname)
        return ip_address

# This class is to log the messages (errors, informations) to the stderr and/or
# stdout. If the settings are correct, it will log also to the error log file
# and/or the info log file.


class Logger(object):

    # The log file from the ini.
    __logFile = None

    # When to rotate the log file.
    __logFileWhen = "midnight"

    # Interval in seconds.
    __logFileInterval = 3600

    # How many files to keep in the history.
    __logFileBackupCount = 10

    # The logger instance.
    __logger = None

    # Create and initialize the logger.
    def __init__(self):
        self.__readConfig()
        if self.__logFile != None:
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler = logging.handlers.TimedRotatingFileHandler(self.__getLogFilePath(), when=self.__logFileWhen, interval=self.__logFileInterval, backupCount=self.__logFileBackupCount)
            handler.setFormatter(formatter)
            self.__logger = logging.getLogger()
            self.__logger.addHandler(handler)
            self.__logger.setLevel(logging.INFO)
        else:
            logging.basicConfig(format="%(asctime)s - %(message)s")

    # Read the ini file if it exists.
    def __readConfig(self):
        parser = configparser.ConfigParser()
        dataset = parser.read(self.__getIniFilePath())
        if len(dataset) > 0:
            self.__version = parser.get(
                GENERAL_SECTION, "version", fallback=None)
            if (self.__version != VERSION):
                sys.stderr.write(f"The configuration file is for version {self.__version} but the script is for version {VERSION}.\n")
                sys.stderr.write(f"Please, upgrade your configuration file to respect the new format.\n")
                sys.stderr.write(f"If you don't know this format, just rename your old ini file and start again\nthe script.\n")
                sys.exit(1)
            self.__logFile = parser.get(LOGGING_SECTION, "logFile", fallback=None)
            self.__logFileWhen = parser.get(LOGGING_SECTION, "logFileWhen", fallback="midnight")
            self.__logFileInterval = parser.getint(LOGGING_SECTION, "logFileInterval", fallback=3600)
            self.__logFileBackupCount = parser.getint(LOGGING_SECTION, "logFileBackupCount", fallback=10)
        else:
            sys.stderr.write("Can't find the configuration file.\n")
            sys.exit(1)

    # Retrieve the path to the ini file.
    def __getIniFilePath(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, CONFIG_FILE)
        return filename

    # Retrieve the path to the log file.
    def __getLogFilePath(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, self.__logFile)
        return filename

    # Log an error message. Write the message to the stderr and if the errorLog
    # parameter is set, write it also to the error log file.
    def error(self, message):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        sys.stderr.write(f"{now} - {message}\n")
        self.__logger.error(message)

    # Log an info message. Write the message to the stdout and if the infoLog
    # parameter is set, write it also to the info log file.
    def info(self, message):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        sys.stdout.write(f"{now} - {message}\n")
        self.__logger.info(message)


print("===================================================")
print("= DNS Updater                                     =")
print("= Script to update the IP address of the A record =")
print("===================================================")

# Update the IP address of the host in the DNS of Gandi
dnsUpdater = DNSUpdater()
dnsUpdater.updateARecords()

print("Bye !")
