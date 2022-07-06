# Quantum Cryptography applied in Quantum Networks
Design of a Quantum Network with Quantum Key Distribution protocols

_by Daniel Espinoza (D-Cryp7) & Nicolás Jara_

## Implementations
### BB84
#### Simple BB84
BB84 Protocol for Quantum Key Distribution in a 2-node Quantum Network . It creates a single Quantum Channel (unidirectional) and two Classsical Channels (bidirectional) with the respective Callback Functions.

Diagram of the Quantum Network:

![](images/Simple%20BB84.jpg)

_ref: https://github.com/h-oll/netsquid-private/blob/master/BB84/BB84.py (adapted by D-Cryp7 for Netsquid 1.1.6)_

### Ekert
#### Basic Entanglement
Generation of entanglement between 2 qubits using Quantum Gates for the Ekert Protocol. Next, the idea is to create a Quantum Network with that QKD Protocol.  
_ref: https://qiskit.org/textbook/ch-gates/multiple-qubits-entangled-states.html (adapted by D-Cryp7 for Netsquid 1.1.6)_

## References
* https://github.com/h-oll/netsquid-private/tree/a894c7c8b1dfc60e70171493991e9cc4f9ac12d3
* https://github.com/FerjaniMY/Quantum_Computing_resources
* https://netsquid.org
* https://qiskit.org
