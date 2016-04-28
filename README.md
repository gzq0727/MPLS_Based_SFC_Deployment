# MPLS_Based_SFC_Deployment
MPLS based Service Chain Deployment Using Ryu controller and mininet
HD_info.txt and NF_info.txt are the input files.HD_info.txt indicates the Service Functions needed of each src-host and dst-host pair.NF_info.txt indicates the detail network function(middlebox) type and location.
SFC_topo.py is the topology we used in this experiment.
Network_aware.py is the module to collect network topology information and calculate all paths between two network nodes.
Network_monitor.py is the module to collect switches' ports statistical information.
SFC_design.py module is the main moudule to deploy Service Chain using MPLS.
the steps of running:
1.copy the SFC_topo.py to the directory mininet/custom
2.copy the other files to the directory ryu/ryu/app
3.start a terminal and cd the directory mininet/custom,then input the following command lines:
 sudo mn --switch ovsk,protocols=OpenFlow13 --custom SFC_topo.py  --topo mytopo  --controller=remote
4.start a new terminal and cd the directory ryu/ryu/app,the input the following command lines:
 sudo ryu-manager --verbose --observe-links SFC_design.py
5.pingall in the mininet in order to get the complete topology information:
mininet:>>pingall
6.wait 30 seconds(defined in the SFC_design.py) after the app is running,we then pingall in the mininet.if it is successful,proving the Service Chains deployment is success.


