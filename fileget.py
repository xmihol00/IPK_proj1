
#=========================================================================================================
# File:        fileget.py
# Case:        VUT, FIT, IPK, project 1
# Date:        19. 3. 2021
# Author:      David Mihola
# Contact:      xmihol00@stud.fit.vutbr.cz
# Interpreted: Python 3.8.5
# Description: Fileget script used for downloading files using UDP and TCP communication.
#==========================================================================================================

import socket
import getopt
import sys
import os
import re
from enum import Enum

class Erros(Enum):
    ARGUMENTS = 1
    IP_ADRESS = 2
    SURL = 3
    SERVER = 4
    CONNECTION = 5
    RESPONSE = 6
    DIRECTORY = 7
    FILE = 8

class Download_state(Enum):
    SUCCESS = 1
    FAIL = 2

class Transfer:
    def __init__(self, name_server, hostname, down_file):
        self.name_server = name_server
        self.down_file = down_file
        self.hostname = hostname
        self.file_server = ()

def parse_argumets():
    """
    Parses the command line arguments. Exits with an error, when the arguments are incorrect.

    Return
    ------
    Transfer
        A transfer object containing name server IP adress and SURL
    """
    nameserver = None
    SURL = None
    try:
        opts, _ = getopt.getopt(sys.argv[1:], "n:f:", [])
    except:
        print("Wrong program arguments, run as: 'python3 fileget.py -n <IP adress and port of a name server> -f <SURL of a fileserver>'",
              "Order of the -n and -f switches does not matter", file=sys.stderr, sep='\n')
        exit(Erros.ARGUMENTS.value)
    
    if len(opts) < 2:
        print("Wrong program arguments, run as: 'python3 fileget.py -n <IP adress and port of a name server> -f <SURL of a fileserver>'",
              "Order of the -n and -f switches does not matter", file=sys.stderr, sep='\n')
        exit(Erros.ARGUMENTS.value)
    
    for arg in opts:
        if arg[0] == "-n":
            nameserver = arg[1].split(':')
            try:
                socket.inet_aton(nameserver[0])
                nameserver[1] = int(nameserver[1])
            except:
                print("'", arg[1], "' is not a valid IP adress", sep='', file=sys.stderr)
                exit(Erros.IP_ADRESS.value)
        if arg[0] == "-f":
            SURL = arg[1].split("//")
            if re.match("^fsp:$", SURL[0], re.IGNORECASE) != None:
                SURL = SURL[1].split('/', 1)
                if len(SURL) != 2:
                    print("'", arg[1], "' is not a valid SURL", sep='', file=sys.stderr)
                    exit(Erros.SURL.value)
                elif re.match(r"^([0-9A-Za-z]|-|_|\.)+$", SURL[0]) == None:
                    print("'", SURL[0], "' is not a valid server name", sep='', file=sys.stderr)
                    exit(Erros.SURL.value)
            else:
                print("'", arg[1], "' is not a valid SURL", sep='', file=sys.stderr)
                exit(Erros.SURL.value)
    
    if SURL == None or nameserver == None or len(nameserver) != 2 or len(SURL) != 2:
        print("Wrong program arguments, run as: 'python3 fileget.py -n <IP adress and port of a name server> -f <SURL of a fileserver>'",
              "Order of the -n and -f switches does not matter", file=sys.stderr, sep='\n')
        exit(Erros.ARGUMENTS.value)

    return Transfer(tuple(nameserver), SURL[0], SURL[1])

def translate_hostname(transfer):
    """
    Performs the translation from SURL to an IP adress of file server with the use of the name server.
    Exits with error when the translation fails (i.e. name server does not respon, invalid SURL, invalid response)

    Parameters
    ----------
    transfer: Transfer
        object which holds the SURL and name server IP

    Return
    ------
    transfer: Transfer
        object recieved as parameter with the file server IP added.
    """
    with socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM) as connection:
        connection.settimeout(31)
        connection.sendto(str.encode("WHEREIS " + transfer.hostname), transfer.name_server)

        try:
            message = connection.recvfrom(1024)
        except:
            name_s = transfer.name_server[0] + ':' + str(transfer.name_server[1])
            print("Connection to name server '", name_s, "' failed.", sep='', file=sys.stderr)
            exit(Erros.CONNECTION.value)

    if len(message) != 2 or message[1] != transfer.name_server:
        print("Invalid response from the name server", file=sys.stderr)
        exit(Erros.RESPONSE.value)

    message = message[0].decode("utf-8").split(' ', 1)
    if message[0] == "OK":
        adress = message[1].split(':', 1)
        try:
            socket.inet_aton(adress[0])
            transfer.file_server = (adress[0], int(adress[1]))
        except:
            print("File server responded with an invalid IP adress or port:", message, file=sys.stderr)
            exit(Erros.IP_ADRESS.value)
    elif message[0] == "ERR":
        print("Server '", transfer.hostname, "' was not found.", sep='', file=sys.stderr)
        exit(Erros.SERVER.value)

    return transfer

def download_file(transfer, request, index = False):
    """
    Downloads a file specified by a tranfser and a request

    Parameters
    ----------
    transfer: Transfer
        An object holding the file server IP adress
    request: byte string
        Bytes representig the request for a file to be downloaded
    index: bool
        True when the file content should be returned as a bite string, otherwise the file is created.

    Return
    ------
    index: byte string
        Byte string with the content of an index file, when specified as parameter.
    bool
        False on success, otherwise True
    """
    with socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM) as connection:
        connection.settimeout(31)
        connection.connect(transfer.file_server)
        connection.sendall(request)
        state = Download_state.SUCCESS

        try:
            message = connection.recv(1024)
            message = message.split(b"\r\n", 3)
            if message[0] == b"FSP/1.0 Success" and message[2] == b'':
                state = Download_state.SUCCESS
            elif (message[0] == b"FSP/1.0 Bad Request" or 
                  message[0] == b"FSP/1.0 Not Found" or 
                  message[0] == b"FSP/1.0 Server Error") and message[2] == b'':
                state = Download_state.FAIL
            else:
                print("Server responded with a message in unsupported format.", file=sys.stderr)
                os._exit(Erros.RESPONSE.value)

            if message[1].startswith(b"Length:"):
                length = int(message[1].strip(b"Length:"))
            else:
                print("Message length could not be parsed.", file=sys.stderr)
                os._exit(Erros.RESPONSE.value)

            content = bytearray(length)
            content[:len(message[3])] = message[3]
            current_lenght = len(message[3])
            while current_lenght < length:
                read = connection.recv_into(memoryview(content)[current_lenght:])
                if read == 0:
                    exit()
                current_lenght += read

            if current_lenght != length:
                exit()

        except:
            print("Lenght of recieved data does not match the lenght specified in the response header.",
                  "Connection to the file server may got interrupted.", file=sys.stderr, sep='\n')
            exit(Erros.CONNECTION.value)

    if state == Download_state.SUCCESS:
        if index:
            return content
        else:
            write_file(transfer, content)
            return False
    elif state == Download_state.FAIL:
        print(content.decode("utf-8"), file=sys.stderr)
        if index:
            exit(Erros.RESPONSE.value)
        return True


def write_file(transfer, content):
    """
    Writes a file specified by a path, if the path does not exist, it is created. Exits with an error when
    either the file or the path cannot be created.

    Parameters
    ----------
    transfer: Transfer
        An object holding the file path.
    
    content: byte string
        A byte string containing the file content.
    """
    path = transfer.down_file.rsplit('/', 1)
    if len(path) > 1 and not os.path.exists(path[0]):
        parts = []
        path = path[0]
        while True:
            path = path.rsplit('/', 1)
            if len(path) == 1:
                path = path[0]
                if not os.path.exists(path):
                    try:
                        os.mkdir(path)
                        path = path + "/"
                    except:
                        print("Unable to create directory:", path, file=sys.stderr)
                        exit(Erros.DIRECTORY.value)
                break
            else:
                parts.append(path[1])
                path = path[0]
                if os.path.exists(path):
                    path = path + '/'
                    break
                
        for direc in reversed(parts):
            try:
                os.mkdir(path + direc)
                path += direc + '/'
            except:
                print("Unable to create directory:", path, file=sys.stderr)
                exit(Erros.DIRECTORY.value)
    try:
        f = open(transfer.down_file, 'wb')
    except:
        print("Unable to open file:", transfer.down_file, file=sys.stderr)
        exit(Erros.FILE.value)

    try:
        f.write(content)
    except:
        print("Unable to write file:", transfer.down_file, file=sys.stderr)
        exit(Erros.FILE.value)
    finally:
        f.close()


def manage_file_download(transfer):
    """
    Manages the download of a file or files when the file name is represented by '*'

    Parameters
    ----------
    transfer: Transfer
        An object holding all necessary info for a file download (i.e. file server host name, IP andress, file name, ...)
    """
    if transfer.down_file == '*':
        request = str.encode("GET index FSP/1.0\r\nHostname: " + transfer.hostname + "\r\nAgent: xmihol00\r\n\r\n")
        index = download_file(transfer, request, True).decode("utf-8").split()
        for filename in index:
            request = str.encode("GET " + filename + " FSP/1.0\r\nHostname: " + transfer.hostname + "\r\nAgent: xmihol00\r\n\r\n")
            transfer.down_file = filename
            download_file(transfer, request)
    else:
        request = str.encode("GET " + transfer.down_file + " FSP/1.0\r\nHostname: " + transfer.hostname + "\r\nAgent: xmihol00\r\n\r\n")
        if download_file(transfer, request):
            exit(Erros.SERVER.value)


transfer = parse_argumets()
translate_hostname(transfer)
manage_file_download(transfer)

exit(0)
