# conding=utf-8
import logging
import struct
import itertools
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
from ryu.lib.packet import  ether_types as ether
from ryu.lib import hub
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import network_aware
import network_monitor
from Create4inputfile import Ryutopoinfo 
from run__MC_ICC16_Alg1 import Run___MC_ICC16_Alg


class SFC_design(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        "Network_Aware": network_aware.Network_Aware,
        "Network_Monitor": network_monitor.Network_Monitor,
    }

    def __init__(self, *args, **kwargs):
        super(SFC_design, self).__init__(*args, **kwargs)
        self.network_aware = kwargs["Network_Aware"]
        self.network_monitor = kwargs["Network_Monitor"]

    	###############################################################################################################
        self.mac_to_port = {}
        self.datapaths = {}        
        self.link_to_port = self.network_aware.link_to_port## links   :(src_dpid,dst_dpid)->(src_port,dst_port)
        self.access_table = self.network_aware.access_table## {sw1,port1 :host1_ip}      
        self.access_ports = self.network_aware.access_ports## dpid->port_num (ports without link)
        self.graph = self.network_aware.graph   
    	
    	
	self.NF = {}	###{'IPS': ['IPS1'], 'LB': ['LB1', 'LB2'], 'IDS': ['IDS1', 'IDS2'], 'FW': ['FW1', 'FW2']}
	self.NF_ConnSw = {}	###{'LB1': '5', 'LB2': '6', 'IPS1': '7', 'IDS2': '4', 'FW1': '1', 'FW2': '3', 'IDS1': '2'}
	self.HD_SFC_index = {}	###{('10.0.0.2', '10.0.0.4'): 1, ('10.0.0.3', '10.0.0.5'): 0, ('10.0.0.1', '10.0.0.5'): 0}
	self.SFC = {}	###{0: ['FW', 'IDS', 'LB'], 1: ['IPS', 'IDS', 'LB']}
	
	self.Sw_NF_Port = {}###Sw_NF_Port[dpid] = NF_Port
	self.Sw_Host_Port = {} ###Sw_Host_Port[swdpid,hostip] = port

	self.SFC_All_Component = {}###{0: [('FW1', 'IDS1', 'LB1'), ('FW1', 'IDS1', 'LB2'), ('FW1', 'IDS2', 'LB1'), ('FW1', 'IDS2', 'LB2'), ('FW2','IDS1','LB1'), ('FW2', 'IDS1', 'LB2'), ('FW2', 'IDS2', 'LB1'), ('FW2', 'IDS2', 'LB2')], 1: [('IPS1', 'IDS1', 'LB1'), ('IPS1', 'IDS1', 'LB2'), ('IPS1', 'IDS2', 'LB1'), ('IPS1', 'IDS2', 'LB2')]}

	self.SFC_All_Component_convert_NF_TO_ConSw = {}###{0: [['1', '2', '5'], ['1', '2', '6'], ['1', '4', '5'], ['1', '4', '6'], ['3', '2', '5'], ['3', '2', '6'], ['3', '4', '5'], ['3', '4', '6']], 1: [['7', '2', '5'], ['7', '2', '6'], ['7', '4', '5'], ['7', '4', '6']]}

	self.SFC_All_detail_pathes = {}####{0:[[[[path1121],[path1122],[path1123]],[[path1231],[path1232],[path1233]]],[[[path2121],[path2122],[path2123]],[[path2231],[path2232],[path2233]]].....],1:[[[[path1121],[path1122],[path1123]],[[path1231],[path1232],[path1233]]],[[[path2121],[path2122],[path2123]],[[path2231],[path2232],[path2233]]].....]}

	self.SFC_All_detail_path = {}###{0:[[[path1121],[path1232]],[[path2122],[path2231]].....],1:[[[path1121],[path1232]],[[path2122],[path2231]]....]}

	self.SFC_Best_Component_Path = {}###{0:[[path1121],[path1232]],1:[[path2122],[path2231]]]

	self.SFC_Best_Component = {}###{0:[['FW1', 'IDS1'],[ 'IDS1','LB1']],1:[['IPS1', 'IDS1'],[ 'IDS1','LB1']]}

	self.HD_Complete_Path = {}###{('10.0.0.2', '10.0.0.4'): [component_pathlist], ('10.0.0.3', '10.0.0.5'): [component_pathlist], ('10.0.0.1','10.0.0.5'): [component_pathlist]}

	self.HD_Access_Sw = {}###{('10.0.0.1'): 5, ('10.0.0.2'): 4,('10.0.0.3'): 3,('10.0.0.4'): 2,('10.0.0.5'): 1}
	
	self.NF_Switch = {}###NF_Switch[dpid]:port
		
	self.SFC_Mpls_Label_Set = {}###	SFC_Mpls_Label_Set[1]:[label1,label2,label3.....]

	self.based_label = 0
	## --- Define two rule-related parameters
    	self.priority = 10			## This parameter indicates the priority of rules
    	self.hardTimeOut_of_a_solution = 120	## This parameter indicates the hard_timeout of rules
	self.usemypath = False## The trigger to start-running of Alg1.

	## --- Define log-files :
    	self.Log_debug = open('SFC_design_log_file.txt','w');   	
	
    	self.apprun_thread = hub.spawn(self._apprun)## Begin to run.

	self.Log_debug.write("=========== SFC_design app  is ready! ==========\n")
    	self.Log_debug.flush()
	
##############################################################################################################################################
    def set_data(self):	
	with open("HD_info.txt",'r') as f1:
	    sfc_index = 0
            for lines in f1:
                line=lines.strip('\n')
                lineContent = line.split('\t')
                SrcipConent = str(lineContent[0]);
                DstipConent = str(lineContent[1]);
                SfCConent= str(lineContent[2]);
		
                One_path = [];
		SfC = SfCConent.split(":")
		
                pathContent = SfC[1].split(">")
                for i in range(0,len(pathContent),1):
                    One_path.append(str(pathContent[i]))
                
		SrcIp = SrcipConent.split(":")		
		DstIp = DstipConent.split(":")
		srcip = SrcIp[1]
		dstip = DstIp[1]

		###self.access_table:{sw1,port1:[host1_ip]  sw1,port2:[host2_ip]} 
		if srcip not in self.HD_Access_Sw.keys():  ##set HD_Access_Sw
			for key,value in self.access_table.items():				
				if value == srcip:						
					self.HD_Access_Sw[srcip] = key[0]					
					break

		if dstip not in self.HD_Access_Sw.keys():  
			for key,value in self.access_table.items():				
				if value == dstip:					
					self.HD_Access_Sw[dstip] = key[0]					
					break		
		
		if One_path not in self.SFC.values():
			self.SFC[sfc_index] = One_path    ##set SFC
			sfc_index+=1   

		for key,value in self.SFC.items():
			if value == One_path:
				self.HD_SFC_index[srcip,dstip] = key   ##set HD_SFC_index

	self.Log_debug.write("HD_Access_Sw: "+str(self.HD_Access_Sw)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	

	self.Log_debug.write("SFC: "+str(self.SFC)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	

	self.Log_debug.write("HD_SFC_index: "+str(self.HD_SFC_index)+"\n")
	self.Log_debug.flush()	
	
	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	with open("NF_info.txt",'r') as f2:
            for lines in f2:
                line=lines.strip('\n')
                lineContent = line.split('\t')
                NFTypeConent = str(lineContent[0]);
                NFNameConent = str(lineContent[1]);
                NFConnSwConent = str(lineContent[2]);
		Sw_NF_PortConent = str(lineContent[3]);
		
                
		NFType = NFTypeConent.split(":")
		if NFType[1] not in self.NF.keys():
			self.NF[NFType[1]] = []

		NFName = NFNameConent.split(":")
		if NFName[1] not in self.NF[NFType[1]]:
			self.NF[NFType[1]].append(NFName[1])  ##set NF

		NFConnSw = NFConnSwConent.split(":")		
		self.NF_ConnSw[NFName[1]] = NFConnSw[1] ##set NF_ConnSw
		
		sw_NF_Port = Sw_NF_PortConent.split(":")		
		self.Sw_NF_Port[NFConnSw[1]] = int(sw_NF_Port[1])###set Sw_NF_Port	
	
	self.Log_debug.write("NF: "+str(self.NF)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	self.Log_debug.write("NF_ConnSw: "+str(self.NF_ConnSw)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()		

	self.Log_debug.write("Sw_NF_Port: "+str(self.Sw_NF_Port)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	for key,value in self.SFC.items():
		self.SFC_All_Component[key] = self.cal_all_component_by_SFCList(value)  ##set SFC_All_Component	
	
	self.Log_debug.write("SFC_All_Component: "+str(self.SFC_All_Component)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()		
	
	for key,value in self.SFC_All_Component.items():##set  SFC_All_Component_convert_NF_TO_ConSw
		self.SFC_All_Component_convert_NF_TO_ConSw[key] = []
		for sfclist in value:
			convert_NF_TO_ConSw_list = []
			for sfc in sfclist:
				convert_NF_TO_ConSw_list.append(self.NF_ConnSw[sfc])
			self.SFC_All_Component_convert_NF_TO_ConSw[key].append(convert_NF_TO_ConSw_list)

	
	self.Log_debug.write("SFC_All_Component_convert_NF_TO_ConSw: "+str(self.SFC_All_Component_convert_NF_TO_ConSw)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	

	
	for key,value in self.SFC_All_Component_convert_NF_TO_ConSw.items():###set SFC_All_detail_pathes
		self.SFC_All_detail_pathes[key] = []		
		
		for sfcConSwList in value:
			
			i=0
			sfc_all_detail_path = []			
			
			if(len(sfcConSwList) == 1):				
				sfc_all_detail_path.append(self.network_aware.getAllPath(sfcConSwList[i],sfcConSwList[i]))
				
			else:				
				while(i+1<len(sfcConSwList)):	
				 	sfc_all_detail_path.append(self.network_aware.getAllPath(sfcConSwList[i],sfcConSwList[i+1]))

				 	i = i +1
			
			self.SFC_All_detail_pathes[key].append(sfc_all_detail_path)			
	
	self.Log_debug.write("SFC_All_detail_pathes: "+str(self.SFC_All_detail_pathes)+"\n")
	self.Log_debug.flush()	
	
	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	
	for key,value in self.SFC_All_detail_pathes.items():###set SFC_All_detail_path
		
		self.SFC_All_detail_path[key] = []
		
		for pathes_list in value:
			one_path = []
			
			for componet_pathes in pathes_list:				
				
				if(len(componet_pathes)<=1):
					one_path.append(componet_pathes[0])
				else:
					one_path.append(self.get_max_speed_path_of_pathes(componet_pathes))	

			self.SFC_All_detail_path[key].append(one_path)
			
	
	self.Log_debug.write("SFC_All_detail_path: "+str(self.SFC_All_detail_path)+"\n")
	self.Log_debug.flush()

	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	
	for key,value in self.SFC_All_detail_path.items():		
		
		speedlist = []
		for one_component_path in value:
			
			speed = float("inf")
			i = 0
			
			while(i<len(one_component_path)):				
					
				pathspeed = self.get_max_speed_of_one_path(one_component_path[i])
				
				if pathspeed <= speed:
					speed = pathspeed
				i = i +1
				
			speedlist.append(speed)
			
		maxspeed = 0
		j = 0
		index = j
		
		while(j<len(speedlist)):
			
			if(speedlist[j] >= maxspeed):
				maxspeed = speedlist[j]
				index = j
			j = j + 1
		
		
		path = value[index]
		
		self.SFC_Best_Component_Path[key] = path ###set  SFC_Best_Component_Path
		
		k = 0
		sw_list = []
		
		if(len(self.SFC[key])<=1):			
			
			for key1,value1 in self.NF_ConnSw.items():
				
				for key2,value2 in self.NF.items():
					
					if key1 in value2:
						if key2 == self.SFC[key][k]:
							if str(value1) == str(path[k][0]):
								sw_list.append(key1)
								break
						
		else:
			
			while(k<len(self.SFC[key])-1):		

				for key1,value1 in self.NF_ConnSw.items():					
					for key2,value2 in self.NF.items():
							
						if key1 in value2:
							
							if key2 == self.SFC[key][k]:
								
								if str(value1) == str(path[k][0]):
						
									sw_list.append(key1)
									break
				k = k+1
			for key1,value1 in self.NF_ConnSw.items():					
					for key2,value2 in self.NF.items():
						
						if key1 in value2:
							if key2 == self.SFC[key][k]:
								if str(value1) == str(path[k-1][-1]):
									

									sw_list.append(key1)
									break		
		
		self.SFC_Best_Component[key] = sw_list###set SFC_Best_Component
		
		
		
        
	self.Log_debug.write("SFC_Best_Component_Path: "+str(self.SFC_Best_Component_Path)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	self.Log_debug.write("SFC_Best_Component: "+str(self.SFC_Best_Component)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	


	for key,value in self.access_table.items():
		swdpid = key[0]
		port = key[1]
		hostip = value
		self.Sw_Host_Port[swdpid,hostip] = port

	self.Log_debug.write("Sw_Host_Port: "+str(self.Sw_Host_Port)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	

##########################################################################################################################################
	for key,value in self.HD_SFC_index.items():###set HD_Complete_Path
		
		HDip = list(key)
		
		complete_path = []
		
		##HD_Access_Sw: {'10.0.0.5': 9, '10.0.0.4': 8, '10.0.0.7': 2, '10.0.0.6': 6, '10.0.0.1': 1, '10.0.0.3': 3, '10.0.0.2': 2}
		
		
		complete_path.append(self.get_max_speed_path_of_pathes(self.network_aware.getAllPath(self.HD_Access_Sw[HDip[0]],self.SFC_Best_Component_Path[value][0][0])))  		
		
		
		for partpath in self.SFC_Best_Component_Path[value]:
			complete_path.append(partpath)		

		complete_path.append(self.get_max_speed_path_of_pathes(self.network_aware.getAllPath(self.SFC_Best_Component_Path[value][-1][-1],self.HD_Access_Sw[HDip[1]])))  
		
		self.HD_Complete_Path[key] = complete_path
		
	
	self.Log_debug.write("HD_Complete_Path: "+str(self.HD_Complete_Path)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()	
	
	self.Log_debug.write("datapaths: "+str(self.datapaths)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()		
		
	for key1,value1 in self.Sw_NF_Port.items():
		for key2,value2 in self.link_to_port.items():

			swdpid = key2[0]
			swport = value2[0]
			nfdpid = key2[1]
			nfport = value2[1]  


			if int(key1) == swdpid and int(value1) == swport:
				self.NF_Switch[nfdpid] = nfport	  ###set  NF_Switch

	self.Log_debug.write("NF_Switch "+str(self.NF_Switch)+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("\n")
	self.Log_debug.flush()		
		
##########################################################################################################################################	
    def design_flow_rule(self):
	eth_IP = ether.ETH_TYPE_IP
        eth_MPLS = ether.ETH_TYPE_MPLS
	
	if self.datapaths and self.SFC_Best_Component_Path and self.Sw_NF_Port and  self.Sw_Host_Port and self.HD_Access_Sw and self.HD_Complete_Path and self.link_to_port:
	####################################################SFC-flow-rule######################################################
		
		for key,value in self.SFC_Best_Component_Path.items():
			i = 0 
			self.SFC_Mpls_Label_Set[key] = []		
			
			self.based_label = self.based_label + 1

			self.SFC_Mpls_Label_Set[key].append(self.based_label)

			while(i < len(value)):
				if len(value[i]) <= 1:###have only one NF or there are two NF linked to one same switch
					
					pass
				else:
					
					j = 0					
					
					while j < len(value[i]):
						
						if j == 0:###the first NF switch 
							
							dpid = value[i][j] 
							nextdpid = value[i][j+1]
							
							dp = self.datapaths[dpid]			
							
							
							in_port = self.Sw_NF_Port[str(dpid)]

							label = self.based_label							
												
							out_port = self.link_to_port[dpid,nextdpid][0]
           
							match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_MPLS,
                        					mpls_label=label)
							
	
							self.based_label = self.based_label + 1
							label = self.based_label
							
							self.SFC_Mpls_Label_Set[key].append(label)

        						f = dp.ofproto_parser.OFPMatchField.make(
            						dp.ofproto.OXM_OF_MPLS_LABEL, label)
							
        						actions = [dp.ofproto_parser.OFPActionPopMpls(eth_IP),
								dp.ofproto_parser.OFPActionPushMpls(eth_MPLS),
                   						dp.ofproto_parser.OFPActionSetField(f),
                  						dp.ofproto_parser.OFPActionOutput(out_port, 0)]
				
							self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
							
							
						elif j == len(value[i]) - 1:###the last NF switch 
							
							dpid = value[i][j] 
							predpid = value[i][j-1]
							
							dp = self.datapaths[dpid]
							in_port = self.link_to_port[predpid,dpid][1]
							out_port = self.Sw_NF_Port[str(dpid)]
							label = self.based_label

							match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_MPLS,
                        					mpls_label=label)
							
        						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]

        						self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
							
							
						else:###middle NF switches							
							dpid = value[i][j]
							predpid = value[i][j-1] 
							nextdpid = value[i][j+1]
							
							dp = self.datapaths[dpid]
							in_port = self.link_to_port[predpid,dpid][1]
							out_port = self.link_to_port[dpid,nextdpid][0]
							label = self.based_label							

							match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_MPLS,
                        					mpls_label=label)
                       						
							
							
        						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]
							
							
							self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)     								
							

						j = j + 1
				i = i+1			
		
	##############################################Host-Margainal-NFSw-flow-rule#########################################
		for key,value in self.HD_Complete_Path.items():###for every (srcip.dstip):[Host_To_SFC_path_list,SFC_path_list,SFC_To_Host_path_list]
			
			sfcindex = self.HD_SFC_index[key]

			push_label = self.SFC_Mpls_Label_Set[sfcindex][0]
			pop_label = self.SFC_Mpls_Label_Set[sfcindex][-1]

			srcip = key[0]
			dstip = key[1]
			
			Host_To_SFC = value[0]
			SFC_To_Host = value[-1]
			i = 0
			while i<len(Host_To_SFC):
				
				if(len(Host_To_SFC)<=1):###the first NF switch is also the access switch
					dpid = 	Host_To_SFC[i]
					
					dp = self.datapaths[dpid]			
					in_port = self.Sw_Host_Port[dpid,srcip]
					out_port = self.Sw_NF_Port[str(dpid)]
					

					
					match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_IP,
                        					ipv4_src=srcip,
                       						ipv4_dst=dstip)
					
        				f = dp.ofproto_parser.OFPMatchField.make(dp.ofproto.OXM_OF_MPLS_LABEL, push_label)
					
					
					actions = [dp.ofproto_parser.OFPActionPushMpls(eth_MPLS),
							dp.ofproto_parser.OFPActionSetField(f),
							dp.ofproto_parser.OFPActionOutput(out_port, 0)]
					self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
		
				else:
					if i == 0:###the fist access switch 

						
						dpid = 	Host_To_SFC[i]
						nextdpid = Host_To_SFC[i+1]
	
						dp = self.datapaths[dpid]			
						in_port = self.Sw_Host_Port[dpid,srcip]
						out_port = self.link_to_port[dpid,nextdpid][0]
						match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_IP,
                        					ipv4_src=srcip,
                       						ipv4_dst=dstip)					
				
						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]
									
						self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
			
					elif i == len(Host_To_SFC)-1:###the last switch in the Host_To_SFC list(is also the access-SFC switch)
						
						dpid = 	Host_To_SFC[i]
						predpid = Host_To_SFC[i-1]
	
						dp = self.datapaths[dpid]			
						in_port =  self.link_to_port[predpid,dpid][1]
						out_port = self.Sw_NF_Port[str(dpid)]
						match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_IP,
                        					ipv4_src=srcip,
                       						ipv4_dst=dstip)
						f = dp.ofproto_parser.OFPMatchField.make(dp.ofproto.OXM_OF_MPLS_LABEL, push_label)
			
						actions = [dp.ofproto_parser.OFPActionPushMpls(eth_MPLS),
								dp.ofproto_parser.OFPActionSetField(f),
								dp.ofproto_parser.OFPActionOutput(out_port, 0)]

						self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
						
					else:###the middle switches in the Host_To_SFC list
						
						dpid = 	Host_To_SFC[i]
						predpid = Host_To_SFC[i-1]
						nextdpid = Host_To_SFC[i+1]
	
						dp = self.datapaths[dpid]			
						in_port = self.link_to_port[predpid,dpid][1]
						out_port = self.link_to_port[dpid,nextdpid][0]
					
						match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_IP,
                        					ipv4_src=srcip,
                       						ipv4_dst=dstip)
			
						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]

						self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
						
				i = i+1			
			
			j = 0
			while j<len(SFC_To_Host):
				if(len(SFC_To_Host)<=1):###the first outgress NF switch  is also the access switch
					dpid = 	SFC_To_Host[j]
	
					dp = self.datapaths[dpid]			
					in_port = self.Sw_NF_Port[str(dpid)]
					out_port = self.Sw_Host_Port[dpid,dstip]
					
					match = dp.ofproto_parser.OFPMatch(                        					
                        					in_port=in_port,
                        					eth_type=eth_MPLS,
                        					mpls_label=pop_label)
					actions = [dp.ofproto_parser.OFPActionPopMpls(eth_IP)]
					
					self.add_flow(dp, 10, match, actions, 0, True, idle_timeout=3600, hard_timeout=3600)

					match = dp.ofproto_parser.OFPMatch(
                        					eth_type=eth_IP,                       					
								ipv4_src=srcip,
                       						ipv4_dst=dstip)

					actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]
					
					self.add_flow(dp, 10, match, actions, 1, False, idle_timeout=3600, hard_timeout=3600)
					
					
				else:
					if j == 0:###the fist outgress switch 
						dpid = 	SFC_To_Host[j]
						nextdpid = SFC_To_Host[j+1]
	
						dp = self.datapaths[dpid]			
						in_port = self.Sw_NF_Port[str(dpid)]
						out_port = self.link_to_port[dpid,nextdpid][0]
						
						match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_MPLS,
                        					mpls_label=pop_label)
	
						actions = [dp.ofproto_parser.OFPActionPopMpls(eth_IP)]
						
						self.add_flow(dp, 10, match, actions, 0, True, idle_timeout=3600, hard_timeout=3600)

						match = dp.ofproto_parser.OFPMatch(
                        					eth_type=eth_IP,                       					
								ipv4_src=srcip,
                       						ipv4_dst=dstip)

						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]
						
						self.add_flow(dp, 10, match, actions, 1, False, idle_timeout=3600, hard_timeout=3600)
						
					elif j == len(SFC_To_Host)-1:###the last switch in the SFC_To_Host list
						dpid = 	SFC_To_Host[j]
						predpid = SFC_To_Host[j-1]
					
						dp = self.datapaths[dpid]
						
						in_port =  self.link_to_port[predpid,dpid][1]	
				
						out_port = self.Sw_Host_Port[dpid,dstip]

						match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_IP,
                        					ipv4_src=srcip,
                       						ipv4_dst=dstip)			
						
						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]

						self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
						
					else:###the middle switches in the SFC_To_Host list
						
						dpid = 	SFC_To_Host[j]
						predpid = SFC_To_Host[j-1]
						nextdpid = SFC_To_Host[j+1]
	
						dp = self.datapaths[dpid]			
						in_port = self.link_to_port[predpid,dpid][1]
						out_port = self.link_to_port[dpid,nextdpid][0]
						
						match = dp.ofproto_parser.OFPMatch(
                        					in_port=in_port,
                        					eth_type=eth_IP,
                        					ipv4_src=srcip,
                       						ipv4_dst=dstip)				
		
						actions = [dp.ofproto_parser.OFPActionOutput(out_port, 0)]

						self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)
						
				j = j+1
		
	####################################################simply-implement-the-NF######################################################
		
		for key,value in self.NF_Switch.items():
			
			dpid = key
			
			dp = self.datapaths[dpid]
			
			in_port = value
			out_port = value	

			match = dp.ofproto_parser.OFPMatch(in_port=in_port,
							eth_type=eth_MPLS)
 
			actions = [dp.ofproto_parser.OFPActionOutput(dp.ofproto.OFPP_IN_PORT,0)]
			
			self.add_flow(dp, 10, match, actions, 0, False, idle_timeout=3600, hard_timeout=3600)

		self.Log_debug.write("self.SFC_Mpls_Label_Set "+str(self.SFC_Mpls_Label_Set)+"\n")
		self.Log_debug.flush()	

		self.Log_debug.write("\n")
		self.Log_debug.flush()	

    def cal_all_component_by_SFCList(self,SFClist):###now it supports to cal max 6 of the length of sfclist
	
	length = len(SFClist)
	all_component = []
	if(length ==1):
		all_component = itertools.product(self.NF[SFClist[0]])
	elif(length ==2):
		all_component = itertools.product(self.NF[SFClist[0]],self.NF[SFClist[1]])
	elif(length ==3):
		all_component = itertools.product(self.NF[SFClist[0]],self.NF[SFClist[1]],self.NF[SFClist[2]])
	elif(length ==4):
		all_component = itertools.product(self.NF[SFClist[0]],self.NF[SFClist[1]],self.NF[SFClist[2]],self.NF[SFClist[3]])
	elif(length ==5):
		all_component = itertools.product(self.NF[SFClist[0]],self.NF[SFClist[1]],self.NF[SFClist[2]],self.NF[SFClist[3]],self.NF[SFClist[4]])
	elif(length ==6):
		all_component = itertools.product(self.NF[SFClist[0]],self.NF[SFClist[1]],self.NF[SFClist[2]],self.NF[SFClist[3]],self.NF[SFClist[4]],self.NF[SFClist[5]])
	else:
		pass
	return list(all_component)	
	
###############################################################################################################################################
##get the link speed between switch1 and switch2

    def get_link_speed(self,switch1_dpid,switch2_dpid): 
	 
	port1=self.link_to_port[(switch1_dpid,switch2_dpid)][0]
	link_speed = self.network_monitor.get_port_speed(switch1_dpid,port1)
	
	return link_speed

####################################################################################################################################
##equal to the min-capacity of one_path  path--eg:{switch1,switch5,switch3,....}

    def get_max_speed_of_one_path(self,path):
	 
	i=0
	maxspeed = 0
	if(len(path)<=1):
		
		maxspeed = float("inf")
		  
		return maxspeed
	while(i+1<len(path)):
		
		linkspeed =  self.get_link_speed(path[i],path[i+1])		
		if maxspeed < linkspeed:
			
			maxspeed = linkspeed
		i = i + 1
	
	return maxspeed

###################################################################################################################
##get the max-capacity path between pathes  pathes--eg:{(pathlist1),(pathlist2),(pathlist3),.......}

    def get_max_speed_path_of_pathes(self,pathes):
	
	j = 0
	min_of_maxspeeds = float("inf")
	max_speed_path_index = j
	while(j<len(pathes)):
		pathspeed = self.get_max_speed_of_one_path(pathes[j])	
		if(min_of_maxspeeds > pathspeed):
			min_of_maxspeeds = pathspeed
			max_speed_path_index = j
		j = j + 1
	
	return pathes[max_speed_path_index]	

######################################################--child process--########################################################################
    def _apprun(self):
	self.Log_debug.write("enter child process"+"\n")
	self.Log_debug.flush()	

	self.Log_debug.write("time  "+str(time.time())+"\n")
	self.Log_debug.flush()

	self.Log_debug.write("child process sleep 30"+"\n")
	self.Log_debug.flush()	

	hub.sleep(30)

	self.Log_debug.write("child process sleep 30 over"+"\n")
	self.Log_debug.flush()

	while self.access_table is None:
		self.Log_debug.write("access table is None,wait 5 seconds"+"\n")
		self.Log_debug.flush()
		hub.sleep(5)

	self.Log_debug.write("access_table"+str(self.access_table)+"\n")
 	self.Log_debug.flush()	

	self.set_data()###get and cal all data needed

	self.Log_debug.write("all data is got,start add flows"+"\n")
	self.Log_debug.flush()	

	self.design_flow_rule()###add flows

	self.Log_debug.write("flows are added over"+"\n")
	self.Log_debug.flush()
	
	self.Log_debug.write("child process over"+"\n")
	self.Log_debug.flush()	
	self.Log_debug.write(" time  "+str(time.time())+"\n")
	self.Log_debug.flush()
	
	
 ##############################################################--Major Function--#############################################################
    
    def add_flow(self, dp, p, match, actions, tableid, goto_table, idle_timeout=0, hard_timeout=0):	

        ofproto = dp.ofproto
        parser = dp.ofproto_parser
	
	if goto_table:
       		 inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions),
			 parser.OFPInstructionGotoTable(1, type_=None, len_=None)]
		
	else:
		inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                            				 actions)]
	
        mod = parser.OFPFlowMod(datapath=dp, table_id=tableid,
				priority=p,command=dp.ofproto.OFPFC_ADD,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst)

	

        dp.send_msg(mod)

	self.Log_debug.write("add a new flow "+"\n")
	self.Log_debug.flush()
	self.Log_debug.write("time  "+str(time.time())+"\n")
	self.Log_debug.flush()

    def install_flow(self, path, flow_info,priority,time,buffer_id, data):
        '''
            path=[dpid1, dpid2, dpid3...]
            flow_info=(eth_type, src_ip, dst_ip, in_port)
        '''
        # first flow entry
        in_port = flow_info[3]
        assert path
        datapath_first = self.datapaths[path[0]]
        ofproto = datapath_first.ofproto
        parser = datapath_first.ofproto_parser
        out_port = ofproto.OFPP_LOCAL

        # inter_link
        if len(path) > 2:
            for i in xrange(1, len(path) - 1):
                port = self.get_link2port(path[i - 1], path[i])
                port_next = self.get_link2port(path[i], path[i + 1])
                if port:
                    src_port, dst_port = port[1], port_next[0]
                    datapath = self.datapaths[path[i]]
                    ofproto = datapath.ofproto
                    parser = datapath.ofproto_parser
                    actions = []

                    actions.append(parser.OFPActionOutput(dst_port))
                    match = parser.OFPMatch(
                        in_port=src_port,
                        eth_type=flow_info[0],
                        ipv4_src=flow_info[1],
                        ipv4_dst=flow_info[2])
                    self.add_flow(
                        datapath, priority, match, actions, 0, False,
                        idle_timeout=time, hard_timeout=time)
		
                    # inter links pkt_out
                    msg_data = None
                    if buffer_id == ofproto.OFP_NO_BUFFER:
                        msg_data = data

                    out = parser.OFPPacketOut(
                        datapath=datapath, buffer_id=buffer_id,
                        data=msg_data, in_port=src_port, actions=actions)

                    datapath.send_msg(out)

        if len(path) > 1:
            # the  first flow entry
            port_pair = self.get_link2port(path[0], path[1])
            out_port = port_pair[0]

            actions = []
            actions.append(parser.OFPActionOutput(out_port))
            match = parser.OFPMatch(
                in_port=in_port,
                eth_type=flow_info[0],
                ipv4_src=flow_info[1],
                ipv4_dst=flow_info[2])
            self.add_flow(datapath_first,
                          priority, match, actions, 0, False, idle_timeout=time, hard_timeout=time)

            # the last hop: tor -> host
            datapath = self.datapaths[path[-1]]
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            actions = []
            src_port = self.get_link2port(path[-2], path[-1])[1]
            dst_port = None

            for key in self.access_table.keys():
                if flow_info[2] == self.access_table[key]:
                    dst_port = key[1]
                    break
            actions.append(parser.OFPActionOutput(dst_port))
            match = parser.OFPMatch(
                in_port=src_port,
                eth_type=flow_info[0],
                ipv4_src=flow_info[1],
                ipv4_dst=flow_info[2])

            self.add_flow(
                datapath, priority, match, actions, 0, False, idle_timeout=time, hard_timeout=time)

            # first pkt_out
            actions = []

            actions.append(parser.OFPActionOutput(out_port))
            msg_data = None
            if buffer_id == ofproto.OFP_NO_BUFFER:
                msg_data = data

            out = parser.OFPPacketOut(
                datapath=datapath_first, buffer_id=buffer_id,
                data=msg_data, in_port=in_port, actions=actions)

            datapath_first.send_msg(out)

            # last pkt_out
            actions = []
            actions.append(parser.OFPActionOutput(dst_port))
            msg_data = None
            if buffer_id == ofproto.OFP_NO_BUFFER:
                msg_data = data

            out = parser.OFPPacketOut(
                datapath=datapath, buffer_id=buffer_id,
                data=msg_data, in_port=src_port, actions=actions)

            datapath.send_msg(out)

        else:  # src and dst on the same
            out_port = None
            actions = []
            for key in self.access_table.keys():
                if flow_info[2] == self.access_table[key]:
                    out_port = key[1]
                    break

            actions.append(parser.OFPActionOutput(out_port))
            match = parser.OFPMatch(
                in_port=in_port,
                eth_type=flow_info[0],
                ipv4_src=flow_info[1],
                ipv4_dst=flow_info[2])
            self.add_flow(
                datapath_first, priority, match, actions, 0 , False,
                idle_timeout=time, hard_timeout=time)

            # pkt_out
            msg_data = None
            if buffer_id == ofproto.OFP_NO_BUFFER:
                msg_data = data

            out = parser.OFPPacketOut(
                datapath=datapath_first, buffer_id=buffer_id,
                data=msg_data, in_port=in_port, actions=actions)

            datapath_first.send_msg(out)


    def get_host_location(self, host_ip):
        for key in self.access_table:
            if self.access_table[key] == host_ip:
                return key
        self.logger.debug("%s location is not found." % host_ip)
        return None


    def get_path(self, graph, src):
        result = self.dijkstra(graph, src)
        if result:
            path = result[1]
            return path
        self.logger.debug("Path is not found.")
        return None


    def get_link2port(self, src_dpid, dst_dpid):
        if (src_dpid, dst_dpid) in self.link_to_port:
            return self.link_to_port[(src_dpid, dst_dpid)]
        else:
            self.logger.debug("Link to port is not found.")
            return None


    def dijkstra(self, graph, src):
        if graph is None:
            self.logger.debug("Graph is empty.")
            return None
        length = len(graph)
        type_ = type(graph)

        # Initiation
        if type_ == list:
            nodes = [i for i in xrange(length)]
        elif type_ == dict:
            nodes = graph.keys()
        visited = [src]
        path = {src: {src: []}}
        if src not in nodes:
            self.logger.debug("Src is not in nodes.")
            return None
        else:
            nodes.remove(src)
        distance_graph = {src: 0}
        pre = next = src
        no_link_value = 100000

        while nodes:
            distance = no_link_value
            for v in visited:
                for d in nodes:
                    new_dist = graph[src][v] + graph[v][d]
                    if new_dist <= distance:
                        distance = new_dist
                        next = d
                        pre = v
                        graph[src][d] = new_dist

            if distance < no_link_value:
                path[src][next] = [i for i in path[src][pre]]
                path[src][next].append(next)
                distance_graph[next] = distance
                visited.append(next)
                nodes.remove(next)
            else:
                self.logger.debug("Next node is not found.")
                return None

        return distance_graph, path	


    ###############################################################################################################	
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
	self.Log_debug.write("pstatechange event function"+"\n")
	self.Log_debug.flush()
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('Register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('Unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
   	self.Log_debug.write("pstatechange event function end"+"\n")
	self.Log_debug.flush()
    ############################################################################################################# 

    '''
    In packet_in handler, we need to learn access_table by ARP.
    Therefore, the first packet from UNKOWN host MUST be ARP.
    '''

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
	self.Log_debug.write("packetin event"+"\n")
	self.Log_debug.flush()
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)

        eth_type = pkt.get_protocols(ethernet.ethernet)[0].ethertype
        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        if isinstance(arp_pkt, arp.arp):
            arp_src_ip = arp_pkt.src_ip
            arp_dst_ip = arp_pkt.dst_ip

	    self.Log_debug.write("arp_ip_src: "+str(arp_src_ip)+" "+"arp_ip_dst: "+str(arp_dst_ip)+"\n")
	    self.Log_debug.flush()

            result = self.get_host_location(arp_dst_ip)
            if result:  # host record in access table.
                datapath_dst, out_port = result[0], result[1]
                actions = [parser.OFPActionOutput(out_port)]
                datapath = self.datapaths[datapath_dst]

                out = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=ofproto.OFP_NO_BUFFER,
                    in_port=ofproto.OFPP_CONTROLLER,
                    actions=actions, data=msg.data)
                datapath.send_msg(out)		
		self.Log_debug.write("arp handle over"+"\n")
	    	self.Log_debug.flush()

            else:       # access info is not existed. send to all host.
                for dpid in self.access_ports:
                    for port in self.access_ports[dpid]:
                        if (dpid, port) not in self.access_table.keys():
                            actions = [parser.OFPActionOutput(port)]
                            datapath = self.datapaths[dpid]
                            out = parser.OFPPacketOut(
                                datapath=datapath,
                                buffer_id=ofproto.OFP_NO_BUFFER,
                                in_port=ofproto.OFPP_CONTROLLER,
                                actions=actions, data=msg.data)
                            datapath.send_msg(out)

        if isinstance(ip_pkt, ipv4.ipv4):

            ip_src = ip_pkt.src
            ip_dst = ip_pkt.dst
	
	    self.Log_debug.write("ip_src: "+str(ip_src)+" "+"ip_dst: "+str(ip_dst)+"\n")
	    self.Log_debug.flush()	
	    

            result = None
            src_sw = None
            dst_sw = None

            src_location = self.get_host_location(ip_src)
            dst_location = self.get_host_location(ip_dst)

            if src_location:
                src_sw = src_location[0]

            if dst_location:
                dst_sw = dst_location[0]
            result = self.dijkstra(self.graph, src_sw)

            if result:
                path = result[1][src_sw][dst_sw]
                path.insert(0, src_sw)
                self.logger.info(
                    " PATH[%s --> %s]:%s\n" % (ip_src, ip_dst, path))

                flow_info = (eth_type, ip_src, ip_dst, in_port)
                self.install_flow(path, flow_info, 1,5,msg.buffer_id, msg.data)
            else:
                # Reflesh the topology database.
                self.network_aware.get_topology(None)
	
   	self.Log_debug.write("packetin handle over"+"\n")
	self.Log_debug.flush()

	self.Log_debug.write("time"+str(time.time())+"\n")
	self.Log_debug.flush()
##################################################### End of This File :~ ################################################
