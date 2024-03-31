#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

mac_addr_table = {}


def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def parse_configs(switchconfig):
    dict_interfaces = {}

    with open(switchconfig,"r") as file:
        priority = file.readline()[0]
        for line in file:
            seq = line.strip().split()
            name = seq[0]
            type = 2 if seq[1] == "T" else 1
            vlan = -2 if seq[1] == "T" else int(seq[1])

            dict_interfaces[name]  = (type,vlan)
    return priority, dict_interfaces    



def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    while True:
        # TODO Send BDPU every second if necessary
        time.sleep(1)

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]
    global mac_addr_table
    conf_interfaces = {}

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    priority, conf_interfaces = parse_configs(f'configs/switch{switch_id}.cfg')

    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        
        

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        print(f'Destination MAC: {dest_mac}')
        print(f'Source MAC: {src_mac}')
        print(f'EtherType: {ethertype}')

        print("Received frame of size {} on interface {}".format(length, interface), flush=True)

        # TODO: Implement forwarding with learning
        mac_addr_table[src_mac] = interface

        int_name = get_interface_name(interface)
        info_src = conf_interfaces[int_name]

        # the first element of conf_interfaces is the type (trunk = 2 access =1)
        # the second element is the vlan if type is acccess, else, if it's trunk,
        # the value is -1

        mac_addr_table[src_mac] = interface

        if(dest_mac != 'ff:ff:ff:ff:ff:ff') :
            if dest_mac in mac_addr_table :

                d_int = mac_addr_table[dest_mac]
                d_int_name = get_interface_name(d_int)
                info_d = conf_interfaces[d_int_name]
                if info_src[0] == 1 : # if source interface has access type
                    if info_d[0] == 1 and info_d[1] == info_src[1]: # destination interface has the same type and vlan_id
                        send_to_link(d_int,data,length)
                    elif info_d[0] == 2: #destination is trunk
                        vlan_tagged_data = data[0:12] + create_vlan_tag(int(info_src[1])) + data[12:]
                        send_to_link(d_int,vlan_tagged_data,length + 4)
                elif info_src[0] == 2 : # if source has trunk type
                    if info_d[0] == 1 and info_d[1] == vlan_id:
                        untagged_data = data[0:12] + data[16:]
                        send_to_link(d_int,untagged_data,length - 4)
                    elif info_d[0] == 2:
                        send_to_link(d_int,data,length)

            else:
                for d in interfaces:
                    if d != interface:
                        d_int_name = get_interface_name(d)
                        info_d = conf_interfaces[d_int_name]
                        if info_src[0] == 1 :   #acccess type
                            if info_d[0] == 1 and info_d[1] == info_src[1] : #access type
                                send_to_link(d,data,length)
                            elif info_d[0] == 2 :   #trunk
                                vlan_tagged_data = data[0:12] + create_vlan_tag(int(info_src[1])) + data[12:]
                                send_to_link(d,vlan_tagged_data,length + 4)
                        elif info_src[0] == 2 : #trunk
                            if info_d[0] == 1 and info_d[1] == vlan_id : #access
                                untagged_data = data[0:12] + data[16:]
                                send_to_link(d,untagged_data,length - 4)
                            elif info_d[0] == 2 : #trunk
                                send_to_link(d,data,length)
                        
        else:
            for d in interfaces:
                if d != interface:
                    d_int_name = get_interface_name(d)
                    info_d = conf_interfaces[d_int_name]
                    if info_src[0] == 1 : #access
                        if info_d[0] == 1 and info_d[1] == info_src[1] : #access
                            send_to_link(d,data,length)
                        elif info_d[0] == 2 : #trunk
                            vlan_tagged_data = data[0:12] + create_vlan_tag(info_src[1]) + data[12:]
                            send_to_link(d,vlan_tagged_data,length + 4)
                    elif info_src[0] == 2 : #trunk
                        if info_d[0] == 1 and info_d[1] == vlan_id : #access
                            untagged_data = data[0:12] + data[16:]
                            send_to_link(d,untagged_data,length - 4)
                        elif info_d[0] == 2 :
                            send_to_link(d,data,length)
                    

        # TODO: Implement VLAN support
        # TODO: Implement STP support

        # data is of type bytes.
        # send_to_link(i, data, length)

if __name__ == "__main__":
    main()
    

