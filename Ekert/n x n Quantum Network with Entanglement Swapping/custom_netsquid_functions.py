from base_netsquid_functions import *
from util import *

def setup_datacollector(network, protocol, path, node_qconnections):
    """
    Setup the datacollector to calculate the fidelity
    when the CorrectionProtocol has finished.

    Parameters
    ----------
    network : :class:`~netsquid.nodes.network.Network`
        Repeater chain network to put protocols on.

    protocol : :class:`~netsquid.protocols.protocol.Protocol`
        Protocol holding all subprotocols used in the network.

    Returns
    -------
    :class:`~netsquid.util.datacollector.DataCollector`
        Datacollector recording fidelity data.

    """

    # Ensure nodes are ordered in the chain:
    # nodes = [network.nodes[name] for name in sorted(network.nodes.keys())]
    nodes = [network.nodes[str(name)] for name in path]
    A_port = int(node_qconnections[nodes[0].name][nodes[1].name].split("-")[0][-1])
    B_port = int(node_qconnections[nodes[-1].name][nodes[-2].name].split("-")[0][-1])
    
    def calc_fidelity(evexpr):
        qubit_a, = nodes[0].qmemory.peek([A_port])
        qubit_b, = nodes[-1].qmemory.peek([B_port])
        fidelity = ns.qubits.fidelity([qubit_a, qubit_b], ks.b00, squared = True)
        return {"fidelity": fidelity}

    dc = DataCollector(calc_fidelity, include_entity_name=False)
    dc.collect_on(pydynaa.EventExpression(source=protocol.subprotocols['CorrectProtocol'],
                                          event_type=Signals.SUCCESS.value))
    return dc

def setup_repeater_protocol(network, path, node_qconnections):
    """Setup repeater protocol on repeater chain network.

    Parameters
    ----------
    network : :class:`~netsquid.nodes.network.Network`
        Repeater chain network to put protocols on.

    Returns
    -------
    :class:`~netsquid.protocols.protocol.Protocol`
        Protocol holding all subprotocols used in the network.

    """
    nodes = [network.nodes[str(name)] for name in path]
    protocol = LocalProtocol(nodes = network.nodes)
    # Add SwapProtocol to all repeater nodes. Note: we use unique names,
    # since the subprotocols would otherwise overwrite each other in the main protocol.
    nodes = [network.nodes[str(name)] for name in path]
    
    port = node_qconnections[nodes[0].name][nodes[1].name].split("-")[0]
    subprotocol = RootProtocol(nodes[0], port)
    protocol.add_subprotocol(subprotocol)
    
    for node in nodes[1:-1]:
        index = path.index(eval(node.name))
        # Specify ccon_R port
        ccon_R = f"ccon_R_{node.name}-{nodes[index + 1].name}"
        port_l = node_qconnections[node.name][nodes[index - 1].name].split("-")[0]
        port_r = node_qconnections[node.name][nodes[index + 1].name].split("-")[0]
        subprotocol = SwapProtocol(node = node, name = f"Swap_{node.name}", ccon_R = ccon_R, port_l = port_l, port_r = port_r)
        protocol.add_subprotocol(subprotocol)
    # Add CorrectProtocol to Bob
    ccon_L = f"ccon_L_{nodes[-2].name}-{nodes[-1].name}"
    # Specify ccon_L port
    port = node_qconnections[nodes[-1].name][nodes[-2].name].split("-")[0]
    subprotocol = CorrectProtocol(nodes[-1], len(nodes), ccon_L, port)
    protocol.add_subprotocol(subprotocol)
    return protocol

def run_simulation(network, qdf, est_runtime, num_iters, traffic, setup_datacollector):
    """
    Run the simulation experiment and return the collected data.

    Parameters
    ----------
    num_nodes : int, optional
        Number of nodes in the path
    node_distance : float, optional
        Distance between nodes, larger than 0. Default 20 [km].
    num_iters : int, optional
        Number of simulation runs. Default 100.

    Returns
    -------
    :class:`pandas.DataFrame`
        Dataframe with recorded fidelity data.

    """
    data_collectors = []
    protocols = []
    for path in traffic["path"]:
        protocol = setup_repeater_protocol(network, path, qdf)
        dc = setup_datacollector(network, protocol, path, qdf)
        data_collectors.append(dc)
        protocols.append(protocol)
    for prot in protocols:
        prot.start()
    # ns.sim_run()
    # print("Simulation started!")
    ns.sim_run(est_runtime * num_iters)
    return data_collectors