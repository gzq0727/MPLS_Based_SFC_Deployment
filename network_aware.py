# conding=utf-8
import logging
import struct
import time
from operator import attrgetter
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp
from ryu.lib import hub
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link

SLEEP_PERIOD = 5
IS_UPDATE = True


class Network_Aware(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _NAME = 'network_aware'

    def __init__(self, *args, **kwargs):
        super(Network_Aware, self).__init__(*args, **kwargs)
        self.name = "Network_Aware"
        self.topology_api_app = self

        # links   :(src_dpid,dst_dpid)->(src_port,dst_port)
        self.link_to_port = {}

        # {(sw,port) :[host1_ip,host2_ip,host3_ip,host4_ip]}
        self.access_table = {}

        # {dpid1:[port1,port2....]}
        self.switch_port_table = {}  # dpid->port_num

        # dpid->port_num (access ports)
        self.access_ports = {}

        # dpid->port_num(interior ports)
        self.interior_ports = {}

        self.outer_ports = {}

        self.graph = {}

        self.pre_link_to_port = {}
        self.pre_graph = {}
        self.pre_access_table = {}

	self.nodelink = {}	
	
	self.debugfile =  open("network_aware_debugfile.txt",'w') ###debug file

 	self.discover_thread = hub.spawn(self._discover)	###start the child processing 

###########################################################################################################################################
       
    def _discover(self):###periodically get topology information

	self.debugfile.write("child processing start"+"\n")
	self.debugfile.flush()
        i = 0
	is_fist_time = True	
        while True:
            self.show_topology()###show topology(topo link,link port,access host)

	    if(is_fist_time and i == 1):###we first get the topology information after the child processing start SLEEP_PERIOD time
		self.get_topology(None)	
		self.set_nodelink()
		is_fist_time = False
	   
            if i == 2:
                self.get_topology(None)	###we reflash the topology data and nodelink per 2*SLEEP_PERIOD

		self.set_nodelink()###set self.nodelink	
                i = 0	  	
	    
            hub.sleep(SLEEP_PERIOD)
            i = i + 1

	self.debugfile.write("child processing over"+"\n")
	self.debugfile.flush()	
   
###############################################################################################################################################
    def getAllPath(self,src,dst):
	src = int(src)
	dst = int(dst)
	
	nodeStack = []
  	pathes = []  

	if(src == dst):	###if src-node and dst-node are the same node,we will return path [src]		
		list1 = []
		list1.append(src)
		pathes.append(list1)
		
	else:	###src-node and dst-node are different nodes 		
		nodeStack.append(src)
  		pathes = self.findPath(nodeStack,src,dst)
  		
	self.debugfile.write("src:"+str(src)+"---->dst:"+str(dst)+"  pathes: "+str(pathes)+"\n")
	self.debugfile.flush()

  	return pathes

    def findPath(self,nodeStack,src,dst):###get all pathes from src to dst using Depth first algorithm	
	pathes = []
  	path = []
  	
  	for node in self.nodelink[src]:
		
      		if node == dst:			
         		for n in nodeStack:
              			path.append(n)			
          		path.append(node)
          		pathes.append(path)
         		
      		elif not node in nodeStack:			
          		nodeStack.append(node)
         	        pathes = pathes+self.findPath(nodeStack,node,dst)

      		else:          		
			pass
          
  	if len(nodeStack):		 
   		 nodeStack.pop()   
		 
  	return pathes

#############################################################################################################################################

    def get_switches(self):###get self.switches
        return self.switches

    def get_links(self):###get self.link_to_port
        return self.link_to_port 

    def get_access_table(self):###get self.access_table
	return self.access_table

############################################################################################################################################

    # get Adjacency matrix from link_to_port
    def get_graph(self, link_list):
        for src in self.switches:
            for dst in self.switches:
                self.graph.setdefault(src, {dst: float('inf')})
                if src == dst:
                    self.graph[src][src] = 0
                elif (src, dst) in link_list:
                    self.graph[src][dst] = 1
                else:
                    self.graph[src][dst] = float('inf')
        return self.graph

#############################################################################################################################################

    def create_port_map(self, switch_list):
        for sw in switch_list:
            dpid = sw.dp.id
            self.switch_port_table.setdefault(dpid, set())
            self.interior_ports.setdefault(dpid, set())
            self.access_ports.setdefault(dpid, set())

            for p in sw.ports:
                self.switch_port_table[dpid].add(p.port_no)###set  self.switch_port_table
    
   
    def create_interior_links(self, link_list):# get links`srouce port to dst port  from link_list
        for link in link_list:
            src = link.src
            dst = link.dst
            self.link_to_port[(src.dpid, dst.dpid)] = (src.port_no, dst.port_no) # link_to_port:(src_dpid,dst_dpid)->(src_port,dst_port)

            # find the access ports and interiorior ports
            if link.src.dpid in self.switches:
                self.interior_ports[link.src.dpid].add(link.src.port_no)
            if link.dst.dpid in self.switches:
                self.interior_ports[link.dst.dpid].add(link.dst.port_no)

    # get ports without link into access_ports
    def create_access_ports(self):
        # we assume that the access ports include outer port.
        # Todo: find the outer ports by filter.
        for sw in self.switch_port_table:
            self.access_ports[sw] = self.switch_port_table[
                sw] - self.interior_ports[sw]

    def create_outer_port(self):
        pass

###############################################################################################################################################

    # show topo
    def show_topology(self):
        switch_num = len(self.graph)
        if self.pre_graph != self.graph or IS_UPDATE:
            print "---------------------Topo Link---------------------"
            print '%10s' % ("switch"),
            for i in xrange(1, switch_num + 1):
                print '%10d' % i,
            print ""
            for i in self.graph.keys():
                print '%10d' % i,
                for j in self.graph[i].values():
                    print '%10.0f' % j,
                print ""
            self.pre_graph = self.graph
        # show link
        if self.pre_link_to_port != self.link_to_port or IS_UPDATE:

            print "---------------------Link Port---------------------"
            print '%10s' % ("switch"),
            for i in xrange(1, switch_num + 1):
                print '%10d' % i,
            print ""

	    #self.file1.write("link_to_port "+str(self.link_to_port)+"\n")

            for i in xrange(1, switch_num + 1):
                print '%10d' % i,
                for j in xrange(1, switch_num + 1):
                    if (i, j) in self.link_to_port.keys():
                        print '%10s' % str(self.link_to_port[(i, j)]),
                    else:
                        print '%10s' % "No-link",
                print ""
            self.pre_link_to_port = self.link_to_port

        # each dp access host
        # {(sw,port) :[host1_ip,host2_ip,host3_ip,host4_ip]}
        if self.pre_access_table != self.access_table or IS_UPDATE:
            print "----------------Access Host-------------------"
            print '%10s' % ("switch"), '%12s' % "Host"
            if not self.access_table.keys():
                print "    NO found host"
            else:
                for tup in self.access_table:
                    print '%10d:    ' % tup[0], self.access_table[tup]
            self.pre_access_table = self.access_table	

###############################################################################################################################################

    def set_nodelink(self):###set the link-info of each nodes
	
	for src in self.graph.keys():
		
		self.nodelink[src] = []
		
	for src in self.graph.keys():
		
		for dst in self.graph[src].keys():

			if self.graph[src][dst] == 1 and dst not in self.nodelink[src]:

				self.nodelink[src].append(dst)

###############################################################################################################################################

    def register_access_info(self, dpid, in_port, ip):###set  self.access_table
        if in_port in self.access_ports[dpid]:
            if (dpid, in_port) in self.access_table:
                if ip != self.access_table[(dpid, in_port)]:
                    self.access_table[(dpid, in_port)] = ip
            else:
                self.access_table[(dpid, in_port)] = ip

###############################################################################################################################################

    def add_flow(self, dp, p, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = dp.ofproto
        parser = dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=dp, priority=p,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst)
        dp.send_msg(mod)

###############################################################################################################################################

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)###listening the switchfeatures events
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        msg = ev.msg
        self.logger.info("switch:%s connected", datapath.id)

        # install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

###############################################################################################################################################

    events = [event.EventSwitchEnter,
              event.EventSwitchLeave, event.EventPortAdd,
              event.EventPortDelete, event.EventPortModify,
              event.EventLinkAdd, event.EventLinkDelete]

    @set_ev_cls(events)###listening events defined above
    def get_topology(self, ev):
        switch_list = get_switch(self.topology_api_app, None)###get switches from the topology api	

        self.create_port_map(switch_list)

        self.switches = self.switch_port_table.keys()

        links = get_link(self.topology_api_app, dpid=None)###get links from the topology api	

        self.create_interior_links(links)
        self.create_access_ports()

        self.get_graph(self.link_to_port.keys())

 
########################################################################################################################################

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)###listening the packetin events
    def _packet_in_handler(self, ev):
	
        msg = ev.msg
        datapath = msg.datapath

        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)

        eth_type = pkt.get_protocols(ethernet.ethernet)[0].ethertype
        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        if arp_pkt:
            arp_src_ip = arp_pkt.src_ip
            arp_dst_ip = arp_pkt.dst_ip

            # record the access info
            self.register_access_info(datapath.id, in_port, arp_src_ip)	


    @set_ev_cls(event.EventLinkDelete, MAIN_DISPATCHER)###listening the linkdelete events
    def linkDeleteHandler(self, ev):
        link_list = get_link(self.topology_api_app, None)        
	self.debugfile.write("linkdelete events happened"+"\n")
	self.debugfile.flush()
        for link in link_list:
            self.debugfile.write(str(link)+"\n")
	    self.debugfile.flush()
	self.debugfile.write("the time is: "+str(time.time())+"\n")
	self.debugfile.flush()
