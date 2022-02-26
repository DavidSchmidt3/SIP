import sipfullproxy
import logging
import socket
import socketserver

PORT = 5060

def main():
    logging.basicConfig(format='%(message)s', filename='SIP.log', level=logging.INFO,
                        datefmt='%H:%M:%S')

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # https://stackoverflow.com/questions/24196932/how-can-i-get-the-ip-address-from-a-nic-network-interface-controller-in-python
    s.connect(("8.8.8.8", 80))
    ipaddress = s.getsockname()[0]

    HOST = ipaddress
    s.close()

    logging.info(f'SIP Proxy zapnutá a beží na IP: {ipaddress}, PORT: {PORT}')
    print(f'SIP Proxy zapnutá a beží na IP: {ipaddress}, PORT: {PORT}')
    sipfullproxy.recordroute = "Record-Route: <sip:%s:%d;lr>" % (ipaddress, PORT)
    sipfullproxy.topvia = "Via: SIP/2.0/UDP %s:%d" % (ipaddress, PORT)

    server = socketserver.UDPServer((HOST, PORT), sipfullproxy.UDPHandler)
    server.serve_forever()

main()
