#    Copyright 2014 Philippe THIRION
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import socketserver
import re
import time
import logging

rx_register = re.compile("^REGISTER")
rx_invite = re.compile("^INVITE")
rx_ack = re.compile("^ACK")
rx_prack = re.compile("^PRACK")
rx_cancel = re.compile("^CANCEL")
rx_bye = re.compile("^BYE")
rx_options = re.compile("^OPTIONS")
rx_subscribe = re.compile("^SUBSCRIBE")
rx_publish = re.compile("^PUBLISH")
rx_notify = re.compile("^NOTIFY")
rx_info = re.compile("^INFO")
rx_message = re.compile("^MESSAGE")
rx_refer = re.compile("^REFER")
rx_update = re.compile("^UPDATE")
rx_from = re.compile("^From:")
rx_cfrom = re.compile("^f:")
rx_to = re.compile("^To:")
rx_cto = re.compile("^t:")
rx_tag = re.compile(";tag")
rx_contact = re.compile("^Contact:")
rx_ccontact = re.compile("^m:")
rx_uri = re.compile("sip:([^@]*)@([^;>$]*)")
rx_addr = re.compile("sip:([^ ;>$]*)")
rx_code = re.compile("^SIP/2.0 ([^ ]*)")
rx_request_uri = re.compile("^([^ ]*) sip:([^ ]*) SIP/2.0")
rx_route = re.compile("^Route:")
rx_contentlength = re.compile("^Content-Length:")
rx_ccontentlength = re.compile("^l:")
rx_via = re.compile("^Via:")
rx_cvia = re.compile("^v:")
rx_branch = re.compile(";branch=([^;]*)")
rx_rport = re.compile(";rport$|;rport;")
rx_contact_expires = re.compile("expires=([^;$]*)")
rx_expires = re.compile("^Expires: (.*)$")

# global dictionnary
recordroute = ""
topvia = ""
registrar = {}


def quotechars(chars):
    return ''.join(['.', c][c.isalnum()] for c in chars)

  
class UDPHandler(socketserver.BaseRequestHandler):
    def changeRequestUri(self):
        md = rx_request_uri.search(self.data[0])
        if md:
            method = md.group(1)
            uri = md.group(2)
            if uri in registrar:
                uri = "sip:%s" % registrar[uri][0]
                self.data[0] = "%s %s SIP/2.0" % (method, uri)

    def removeRouteHeader(self):
        data = []
        for line in self.data:
            if not rx_route.search(line):
                data.append(line)
        return data

    def addTopVia(self):
        branch = ""
        data = []
        for line in self.data:
            if rx_via.search(line) or rx_cvia.search(line):
                md = rx_branch.search(line)
                if md:
                    branch = md.group(1)
                    via = "%s;branch=%sm" % (topvia, branch)
                    data.append(via)
                # rport processing
                if rx_rport.search(line):
                    text = "received=%s;rport=%d" % self.client_address
                    via = line.replace("rport", text)
                else:
                    text = "received=%s" % self.client_address[0]
                    via = "%s;%s" % (line, text)
                data.append(via)
            else:
                data.append(line)
        return data

    def removeTopVia(self):
        data = []
        for line in self.data:
            if rx_via.search(line) or rx_cvia.search(line):
                if not line.startswith(topvia):
                    data.append(line)
            else:
                data.append(line)
        return data

    def getSocketInfo(self, uri):
        addrport, socket, client_addr = registrar[uri]
        return (socket, client_addr)

    def getDestination(self):
        destination = ""
        for line in self.data:
            if rx_to.search(line) or rx_cto.search(line):
                md = rx_uri.search(line)
                if md:
                    destination = "%s@%s" % (md.group(1), md.group(2))
                break
        return destination

    def getOrigin(self):
        origin = ""
        for line in self.data:
            if rx_from.search(line) or rx_cfrom.search(line):
                md = rx_uri.search(line)
                if md:
                    origin = "%s@%s" % (md.group(1), md.group(2))
                break
        return origin

    def sendResponse(self, code):
        request_uri = "SIP/2.0 " + code
        self.data[0] = request_uri
        index = 0
        data = []
        for line in self.data:
            data.append(line)
            if rx_to.search(line) or rx_cto.search(line):
                if not rx_tag.search(line):
                    data[index] = "%s%s" % (line, ";tag=123456")
            if rx_via.search(line) or rx_cvia.search(line):
                # rport processing
                if rx_rport.search(line):
                    text = "received=%s;rport=%d" % self.client_address
                    data[index] = line.replace("rport", text)
                else:
                    text = "received=%s" % self.client_address[0]
                    data[index] = "%s;%s" % (line, text)
            if rx_contentlength.search(line):
                data[index] = "Content-Length: 0"
            if rx_ccontentlength.search(line):
                data[index] = "l: 0"
            index += 1
            if line == "":
                break
        data.append("")
        text = "\r\n".join(data).encode('utf-8')
        self.socket.sendto(text, self.client_address)

    def processRegister(self):
        fromm = ""
        contact = ""
        contact_expires = ""
        header_expires = ""
        expires = 0
        for line in self.data:
            if rx_to.search(line) or rx_cto.search(line):
                md = rx_uri.search(line)
                if md:
                    fromm = "%s@%s" % (md.group(1), md.group(2))
            if rx_contact.search(line) or rx_ccontact.search(line):
                md = rx_uri.search(line)
                if md:
                    contact = md.group(2)
                else:
                    md = rx_addr.search(line)
                    if md:
                        contact = md.group(1)
                md = rx_contact_expires.search(line)
                if md:
                    contact_expires = md.group(1)
            md = rx_expires.search(line)
            if md:
                header_expires = md.group(1)

        if len(contact_expires) > 0:
            expires = int(contact_expires)
        elif len(header_expires) > 0:
            expires = int(header_expires)

        if expires == 0:
            if fromm in registrar:
                del registrar[fromm]
                self.sendResponse("200 VYBAVENE 0K")
                return
        else:
            now = int(time.time())

        registrar[fromm] = [contact, self.socket, self.client_address]
        self.sendResponse("200 VYBAVENE 0K")

    def processInvite(self):
        origin = self.getOrigin()
        originName = origin.split('@')[0]

        if len(origin) == 0 or not origin in registrar:
            self.sendResponse("400 Zly request")
            return
        destination = self.getDestination()
        destinationName = destination.split('@')[0]
        callID = self.getCallID()

        if len(destination) > 0:
            logging.info("??as vyt????ania: " + time.strftime("%H:%M:%S", time.localtime()) + f", ID hovoru:{callID}")
            for key in registrar:
                keyName = key.split('@')[0]
                if originName == keyName:
                    originToLog = registrar[key][0]    
                    originToLogIP = originToLog.split(":")[0]
                    originToLogPort = originToLog.split(":")[1]
                    logging.info(f"Meno zah??jovate??a hovoru: {originName}, IP: {originToLogIP}, PORT: {originToLogPort}, ID hovoru:{callID}")

                if destinationName == keyName:
                    destinationToLog = registrar[key][0]
                    destinationToLogIP = destinationToLog.split(":")[0]
                    destinationToLogPort = destinationToLog.split(":")[1]
                    logging.info(f"Meno prij??mate??a hovoru: {destinationName}, IP: {destinationToLogIP}, PORT: {destinationToLogPort}, ID Hovoru:{callID}")
            
            if destination in registrar:
                socket, claddr = self.getSocketInfo(destination)
                self.data = self.addTopVia()
                data = self.removeRouteHeader()
                data.insert(1, recordroute)
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)
            else:
                self.sendResponse("480 Do??asne nedostupne")
        else:
            self.sendResponse("500 Interny server error")

    def processAck(self):
        destination = self.getDestination()
        if len(destination) > 0:
            if destination in registrar:
                callID = self.getCallID()
                socket, claddr = self.getSocketInfo(destination)
                logging.info("??as prijatia hovoru: " + time.strftime("%H:%M:%S", time.localtime()) + f", ID Hovoru:{callID}")
                self.data = self.addTopVia()
                data = self.removeRouteHeader()
                data.insert(1, recordroute)
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)

    def getCallID(self):
        for item in self.data:
            if item.split(':')[0] == 'Call-ID':
                return item.split(':')[1]
        return 'Unknown ID'

    def processNonInvite(self):
        origin = self.getOrigin()
        request_uri = self.data[0]
        callID = self.getCallID()
        if rx_bye.search(request_uri):
            logging.info(f"Hovor ukon??en??, ID hovoru:{callID}, ??as ukon??enia: " + time.strftime("%H:%M:%S", time.localtime()))
        if len(origin) == 0 or not origin in registrar:
            self.sendResponse("400 Zly Request")
            return
        destination = self.getDestination()
        if len(destination) > 0:
            if destination in registrar:
                socket, claddr = self.getSocketInfo(destination)
                self.data = self.addTopVia()
                data = self.removeRouteHeader()
                data.insert(1, recordroute)
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)
            else:
                self.sendResponse("406 Neda sa prija??")
        else:
            self.sendResponse("500 Interny server error")

    def processCode(self):
        origin = self.getOrigin()
        if len(origin) > 0:
            if origin in registrar:
                socket, claddr = self.getSocketInfo(origin)
                self.data = self.removeRouteHeader()
                data = self.removeTopVia()
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)

    def processRequest(self):
        if len(self.data) > 0:
            request_uri = self.data[0]
            if rx_register.search(request_uri):
                self.processRegister()
            elif rx_invite.search(request_uri):
                self.processInvite()
            elif rx_ack.search(request_uri):
                self.processAck()
            elif rx_bye.search(request_uri) or\
                rx_cancel.search(request_uri) or\
                rx_info.search(request_uri) or\
                rx_message.search(request_uri) or\
                rx_refer.search(request_uri) or\
                rx_prack.search(request_uri) or\
                rx_update.search(request_uri):
                self.processNonInvite()
            elif rx_subscribe.search(request_uri) or\
                rx_publish.search(request_uri) or\
                rx_notify.search(request_uri):
                self.sendResponse("200 VYBAVENE 0K")
            elif rx_code.search(request_uri):
                self.processCode()

    def handle(self):
        if self.request[0] == '0x80':
            return
        data = self.request[0].decode('utf-8', errors='ignore')
        self.data = data.split("\r\n")
        self.socket = self.request[1]
        request_uri = self.data[0]
        if rx_request_uri.search(request_uri) or rx_code.search(request_uri):
            self.processRequest()
