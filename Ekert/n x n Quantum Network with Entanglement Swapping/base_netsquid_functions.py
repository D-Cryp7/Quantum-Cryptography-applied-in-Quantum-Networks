import pandas
import pydynaa
import numpy as np
from random import randint
from util import *

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Util.number import long_to_bytes
from hashlib import sha256

import netsquid as ns
from netsquid.qubits import ketstates as ks
from netsquid.components import Message, QuantumProcessor, QuantumProgram, PhysicalInstruction
from netsquid.components.models.qerrormodels import DepolarNoiseModel, DephaseNoiseModel, QuantumErrorModel
from netsquid.components.instructions import INSTR_MEASURE_BELL, INSTR_X, INSTR_Z
from netsquid.nodes import Node, Network
from netsquid.protocols import LocalProtocol, NodeProtocol, Signals
from netsquid.util.datacollector import DataCollector
from netsquid.examples.teleportation import EntanglingConnection, ClassicalConnection

def random_basis():
    r = randint(0, 1)
    return ns.Z if r else ns.X

def measure(q, obs):
    measurement_result, prob = ns.qubits.measure(q, obs)
    if measurement_result == 0:
        state = "|0>" if obs == ns.Z else "|+>"
    else:
        state = "|1>" if obs == ns.Z else "|->"
    return ("Z" if obs == ns.Z else "X"), measurement_result, prob

class FibreDepolarizeModel(QuantumErrorModel):
    """
    Custom non-physical error model used to show the effectiveness
    of Entanglement Swapping.

    The default values are chosen to make a nice figure,
    and don't represent any physical system.

    Parameters
    ----------
    p_depol_init : float, optional
        Probability of depolarization on entering a fibre.
        Must be between 0 and 1. Default 0.009
    p_depol_length : float, optional
        Probability of depolarization per km of fibre.
        Must be between 0 and 1. Default 0.025

    """

    def __init__(self, p_depol_init = 0.009, p_depol_length = 0.025):
        super().__init__()
        self.properties['p_depol_init'] = p_depol_init
        self.properties['p_depol_length'] = p_depol_length
        self.required_properties = ['length']

    def error_operation(self, qubits, delta_time = 0, **kwargs):
        """
        Uses the length property to calculate a depolarization probability,
        and applies it to the qubits.

        Parameters
        ----------
        qubits : tuple of :obj:`~netsquid.qubits.qubit.Qubit`
            Qubits to apply noise to.
        delta_time : float, optional
            Time qubits have spent on a component [ns]. Not used.

        """
        for qubit in qubits:
            prob = 1 - (1 - self.properties['p_depol_init']) * np.power(
                10, - kwargs['length'] ** 2 * self.properties['p_depol_length'] / 10)
            ns.qubits.depolarize(qubit, prob = prob)
            
class SwapCorrectProgram(QuantumProgram):
    """
    Quantum processor program that applies all swap corrections.
    """
    
    default_num_qubits = 1

    def set_corrections(self, x_corr, z_corr):
        self.x_corr = x_corr % 2
        self.z_corr = z_corr % 2

    def program(self):
        q1, = self.get_qubit_indices(1)
        if self.x_corr == 1:
            self.apply(INSTR_X, q1)
        if self.z_corr == 1:
            self.apply(INSTR_Z, q1)
        yield self.run()
        
def create_qprocessor(name):
    """
    Factory to create a quantum processor for each node in the Quantum Network.

    Has four memory positions and the physical instructions necessary for teleportation.

    Parameters
    ----------
    name : str
        Name of the quantum processor.

    Returns
    -------
    :class:`~netsquid.components.qprocessor.QuantumProcessor`
        A quantum processor to specification.

    """
    noise_rate = 200
    gate_duration = 1
    gate_noise_model = DephaseNoiseModel(noise_rate)
    mem_noise_model = DepolarNoiseModel(noise_rate)
    physical_instructions = [
        PhysicalInstruction(INSTR_X, duration=gate_duration,
                            quantum_noise_model=gate_noise_model),
        PhysicalInstruction(INSTR_Z, duration=gate_duration,
                            quantum_noise_model=gate_noise_model),
        PhysicalInstruction(INSTR_MEASURE_BELL, duration=gate_duration),
    ]
    # 4 qubit processor
    qproc = QuantumProcessor(name, num_positions=4, fallback_to_nonphysical=False,
                             mem_noise_models=[mem_noise_model] * 4,
                             phys_instructions=physical_instructions)
    return qproc

class SwapProtocol(NodeProtocol):
    """
    Perform Swap on a repeater node.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node` or None, optional
        Node this protocol runs on.
    name : str
        Name of this protocol.

    """

    def __init__(self, node, name, ccon_R, port_l, port_r):
        super().__init__(node, name)
        self._qmem_input_port_l = self.node.qmemory.ports[port_l]
        self._qmem_input_port_r = self.node.qmemory.ports[port_r]
        self._program = QuantumProgram(num_qubits = 2)
        self.ccon_R = ccon_R
        q1, q2 = self._program.get_qubit_indices(num_qubits = 2)
        self._program.apply(INSTR_MEASURE_BELL, [q1, q2], output_key = "m", inplace = False)

    def run(self):
        while True:
            yield (self.await_port_input(self._qmem_input_port_l) &
                   self.await_port_input(self._qmem_input_port_r))
            # Perform Bell measurement
            yield self.node.qmemory.execute_program(self._program, 
                                                    qubit_mapping=[int(self._qmem_input_port_l.name[-1]), 
                                                                   int(self._qmem_input_port_r.name[-1])])
            m, = self._program.output["m"]
            # Send result to right node on end
            self.node.ports[self.ccon_R].tx_output(Message(m))
            # print(f"Message swapped from {self.ccon_R}: {m}") # for debugging
            
class CorrectProtocol(NodeProtocol):
    """
    Perform corrections for a swap on an end-node.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node` or None, optional
        Node this protocol runs on.
    num_nodes : int
        Number of nodes in the path.

    """

    def __init__(self, node, num_nodes, ccon_L, port):
        super().__init__(node, "CorrectProtocol")
        self._qmem_input_port = self.node.qmemory.ports[port]
        self.num_nodes = num_nodes
        self._x_corr = 0
        self._z_corr = 0
        self._program = SwapCorrectProgram()
        self._counter = 0
        self.ccon_L = ccon_L

    def run(self):
        while True:
            if self.num_nodes > 2:
                yield self.await_port_input(self.node.ports[self.ccon_L])
                message = self.node.ports[self.ccon_L].rx_input()
                if message is None or len(message.items) != 1:
                    continue
                m = message.items[0]
                if m == ks.BellIndex.B01 or m == ks.BellIndex.B11:
                    self._x_corr += 1
                if m == ks.BellIndex.B10 or m == ks.BellIndex.B11:
                    self._z_corr += 1
                self._counter += 1
                if self._counter == self.num_nodes - 2:
                    if self._x_corr or self._z_corr:
                        self._program.set_corrections(self._x_corr, self._z_corr)
                        yield self.node.qmemory.execute_program(self._program, qubit_mapping=[1])
                    self.send_signal(Signals.SUCCESS)
                    self._x_corr = 0
                    self._z_corr = 0
                    self._counter = 0
                    # print(f"Message recieved and corrected from {self.ccon_L}: {m}") # for debugging
            else:
                yield self.await_port_input(self._qmem_input_port)
                self.send_signal(Signals.SUCCESS)
                # print(f"Message recieved from {self.ccon_L}") # for debugging
                
def network_setup(n, node_distance, source_frequency):
    
    """
    n x n grid Quantum Network setup.
    - based on Multipath Routing for Multipartite State Distribution in Quantum Networks
    - each node can do Entanglement Swapping

    Parameters:
    - node_distance (float): Distance between nodes [km]
    - source_frecuency (float): Frequency at which the sources create entangled qubits [Hz]

    Returns:
    - class:`~netsquid.nodes.network.Network`
      Network component with all nodes and connections as subcomponents.

    ref: https://docs.netsquid.org/latest-release/learn_examples/learn.examples.repeater_chain.html
    """
    network = Network(f"{n}x{n} grid Quantum Network")
    # Create nodes with quantum processors
    nodes = []
    
    node_qconnections = {}
    node_used_ports = {}
    quantum_ports = ["qin" + str(i) for i in range(4)] # 4 memory positions for the QuantumProcessor
    
    for i in range(n):
        for j in range(n):
            nodes.append(Node(f"{i,j}", qmemory = create_qprocessor(f"qproc_{i,j}")))
            node_qconnections[f"({i}, {j})"] = {}
            node_used_ports[f"({i}, {j})"] = []
    network.add_nodes(nodes)
    # Create quantum and classical connections:
    for i in range(len(nodes)):
        current_node = nodes[i]
        neighbours = get_neighbours(network, current_node, n)
        for near in neighbours:
            # print("Establishing a connection: ", current_node.name, "->", near.name) # for debugging
            # Create quantum connection
            try:       
                qconn = EntanglingConnection(name =f"qconn_{current_node.name}<->{near.name}", 
                                             length = node_distance,
                                             source_frequency = source_frequency)
                # Add a noise model which depolarizes the qubits exponentially
                # depending on the connection length
                for channel_name in ['qchannel_C2A', 'qchannel_C2B']:
                    qconn.subcomponents[channel_name].models['quantum_noise_model'] =\
                        FibreDepolarizeModel()
                
                port_name, port_r_name = network.add_connection(
                    current_node, near, connection = qconn, label="quantum")
                
                for l_port in quantum_ports:
                    if l_port not in node_used_ports[current_node.name]:
                        node_used_ports[current_node.name].append(l_port)
                        break
                
                for r_port in quantum_ports:
                    if r_port not in node_used_ports[near.name]:
                        node_used_ports[near.name].append(r_port)
                        break
                        
                node_qconnections[current_node.name][near.name] = str(l_port) + "-" + str(r_port)
                node_qconnections[near.name][current_node.name] = str(r_port) + "-" + str(l_port)
                
                # Forward qconn directly to quantum memories for right and left inputs:
                current_node.ports[port_name].forward_input(current_node.qmemory.ports[str(l_port)])
                near.ports[port_r_name].forward_input(near.qmemory.ports[str(r_port)])
            except:
                pass
            
            # Create classical connection
            cconn = ClassicalConnection(name = f"cconn_{current_node.name}-{near.name}", length = node_distance)
            port_name, port_r_name = network.add_connection(
                current_node, near, connection = cconn, label="classical",
                port_name_node1 = f"ccon_R_{current_node.name}-{near.name}", port_name_node2 = f"ccon_L_{current_node.name}-{near.name}")
            # Forward cconn to right most node
            if f"ccon_L_{current_node.name}-{near.name}" in current_node.ports:
                current_node.ports[f"ccon_L_{current_node.name}-{near.name}"].bind_input_handler(
                    lambda message, _node = current_node: _node.ports[f"ccon_R_{current_node.name}-{near.name}"].tx_output(message))
    return network, node_qconnections