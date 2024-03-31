# ethernet_switch

This project represents the implementation of a simple Ethernet switch that populates the MAC table and forwards packets based on the source and destination interface types.

I have created a function that parses the configuration files of the switches and extracts data about interfaces: the keys are their names, and the corresponding value is represented by a pair <type, vlan> (type = 1 -> access, type = 2 -> trunk).

For each hop, the function looks up the information about the source interface and the destination interface in the dictionary. Depending on their type, four cases are differentiated: access-access, access-trunk, and vice versa.

It checks if the destination MAC address is unicast, if it is contained in the table or not, and handles all the mentioned cases above.

In the case where the source-destination interfaces do not have the same type, modifications are made to the packet data: the VLAN tag is removed or added accordingly, and the buffer length increases/decreases by 4 bytes.

