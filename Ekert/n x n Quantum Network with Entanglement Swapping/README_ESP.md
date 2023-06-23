# Entanglement Swapping Analysis in Grid Quantum Networks
##### Comentarios sobre la implementación
##### by D-Cryp7

## Introducción

Considerando que en la documentación de NetSquid no se encuentra ningún ejemplo relacionado a la creación de una red cuántica arbitraria, este proyecto pretende basarse en el Repeater Chain para entrelazar cualquier par de nodos en una red cuántica de tipo Grilla.

El Repeater Chain (https://docs.netsquid.org/latest-release/learn_examples/learn.examples.repeater_chain.html) es un ejemplo que tiene NetSquid en su documentación, donde se entrelazan 2 nodos usando el Entanglement Swapping, pero para una red muy simple, es sólo una cadena de repetidores, donde la comunicación va hacia una única dirección, no existe enrutamiento como tal.

¿Cómo extender esto? Bueno, la idea es definir una red de tipo Grilla, donde se va a instanciar el Repeater Chain para la ruta que yo quiera. Cabe destacar que es posible entrelazar más de una ruta en la misma simulación, pero todas deben ser disjuntas entre sí, esa es la condición actual.

## Configuración de la red

El ejemplo del Repeater Chain funciona del tal manera que, entre cada nodo, existe una Quantum Source que genera entrelazamiento en el enlace. El usuario puede perillar los siguientes parámetros:
* El tamaño de la red ($n$ x $n$)
* La distancia entre nodos (_node\_distance_)
* El número de pulsos que realiza la Quantum Source, o bien, el número de iteraciones en la simulación (_num\_iters_)
* El tiempo estimado (por iteración) de la simulación (_est\_runtime_). NetSquid funciona a través de eventos en tiempos discretos y, en este caso, el número de eventos nunca acaba, supongo que por los constantes pulsos que realiza la Quantum Source. En la documentación se comenta al respecto, y es por eso que se define un tiempo estático a la simulación, tomado el ejemplo del Repeater Chain y luego perillado un poco en la versión de QKD para ver si realmente ese tiempo es representativo o no (https://docs.netsquid.org/latest-release/api_util/netsquid.util.simtools.html?highlight=sim_run#netsquid.util.simtools.sim_run)
    * > "It can be the case that there will always be a new event in the timeline. In this case, not passing an end_time or a duration to the run may cause a never ending simulation."

## Código

Las secciones anteriores eran para contextualizar un poco. Ahora, voy a describir cada parte del código.

### `base_netsquid_functions.py`

Aquí se encuentran funciones de NetSquid que no se modificaron mucho, aunque igual hay un par que implementé yo:

* `random_basis`: Genera una base random, estándar (Z) o Hadamard (X), para aplicaciones de QKD.
* `measure`: Mide un qubit utilizando la base Z o X, para aplicaciones de QKD.
* `FibreDepolarizeModel`: Clase que describe el modelo de error para la transmisión de los qubits. Es el modelo por defecto, no se le ha cambiado nada.
* `SwapCorrectProgram`: Clase que describe parte del proceso a realizar para las correciones finales del qubit recibido, creo que esto es Entanglement Purification. No se le ha modificado nada respecto al ejemplo del Repeater Chain.
* `create_qprocessor`: Describe las acciones que puede realizar el nodo. Lo único que se modificó es que `num_positions` es igual a 4, antes eran 2.
* `SwapProtocol`: Clase que realiza el Entanglement Swapping, para cada nodo intermedio de la ruta, recordar que el nodo inicial no hace absolutamente nada, sólo recibe el estado entrelazado de la Quantum Source. El nodo final hace las correcciones, y los nodos intermedios hacen el Swapping. Como estamos hablando de una red cuántica donde hay distintos caminos, lo que se modificó acá viene dado por la asignación de puertos y las conexiones que consideran la ruta respectiva. Dicho de otra manera, `ccon_R` es el nodo siguiente de la ruta, `port_l` es el puerto del nodo anterior y `port_r` es el puerto del nodo siguiente. Estos dos últimos puertos son para realizar el Entanglement Swapping correctamente. Toda esta información viene dada por la matriz de conectividad, descrita más adelante.
* `CorrectProtocol`: Clase que describe lo que realiza el nodo final, es decir, el Entanglement Purification. `ccon_L` es la conexión al nodo anterior, y `port` es el puerto del nodo final de donde se saca el qubit.
* `RootProtocol`: Clase que describe lo que realiza el nodo inicial. Esto originalmente no estaba, lo puse sólo para estudiar si es que todos los qubits llegaban al nodo inicial, desde la Quantum Source.
* `network_setup`: Esta función es clave, ya que define la red completa. Se realiza lo siguiente:
    * Se crean $n$ x $n$ nodos, cada uno con su procesador mientras inicializamos la matriz de conexiones y los puertos usados. A continuación, los nodos se agregan a la red, lo que queremos hacer es ir trackeando los puertos que se conectan entre cada nodo.
    * Obtengo el primer nodo y calculo sus vecinos directos. Con ello, se realizan conexiones del canal cuántico y clásico para cada uno de los vecinos, procurando que no esté usando un puerto que ya se ocupó anteriormente. `EntanglingConnection` es la conexión que genera la Quantum Source entre ambos nodos, donde se agrega además la `FibreDepolarizeModel` en cada canal cuántico.
    * La matriz de conectividad tiene como objetivo saber la conexión entre puertos de cada nodo, de tal manera de utilizarlo cuando quiera asignar los protocolos de Swap y Correct a cualquier ruta. Para más información, ver mi paper.
    * Los puertos son en relación a las conexiones del canal cuántico. Falta el clásico, y eso es lo que efectivamente se realiza a continuación.
    * Con todo esto, retornamos la red completa y la matriz de conexiones. ¿Qué pasa con la matriz de conexiones del canal clásico? Bueno, no es necesario hacer una, ya que forma parte del nombre de la conexión!

### `custom_netsquid_functions.py`
Estas son funciones que cambiaron bastante, quizás al nivel del `network_setup`, como se comentó en la sección anterior.

* `setup_datacollector`: La función más básica que genera el dataframe. No lo comenté antes, pero en el `CorrectProtocol` hay una parte donde se manda la señal "SUCCESS". Bueno, esa señal gatilla esta función, haciendo que cuando llegue cada qubit se registre la fidelidad entre el qubit del nodo inicial y el qubit del nodo final, además de un timestamp (no se muestra en el código, es automático). Ya veremos más adelante que este código es sobreescrito para simular en otros contextos, como en QKD.
* `setup_repeater_protocol`: Aquí se definen los protocolos para cada nodo que esté en el path que queramos analizar. El nodo inicial no hace nada, los nodos intermedios hacen el Swap, y el nodo final hace el Purification.
* `run_simulation`: Lo más importante, la simulación. Esto está diseñado para considerar varias rutas al mismo tiempo, siempre y cuando sean disjuntas. Sin embargo, la mayoría de tests sólo consideran una, pero el primer `for` está para considerar varias por si acaso. Definimos los protocolos, los _data collectors_, iniciamos cada protocolo, y la simulación comienza en el tiempo estimado. Debido a que _est\_runtime_ es el tiempo por iteración, multiplicamos por _num\_iters_.

### `util.py`

Funciones random, no tienen que ver con NetSquid.

* `zero_runs`: Contar cuántos ceros seguidos hay en una lista. Se utiliza para calcular el Attemps Util Successful Entanglement (AUSE), lo comentaré más adelante.
* `move`: Función útil para escoger una ruta aleatoria en la Grid Quantum Network (GQN)
* `get_random_route`: No quise hacer funciones de búsqueda, así que sólo creé una función que me genere una ruta random entre 2 nodos random. Ojo que esto sólo aplica para una red de tipo grilla.
* `binary_entropy`: Función útil para calcular el Secret Key Rate (SKR), lo comentaré más adelante.
* `get_neighbours`: Obtener los vecinos directos. Se usa para generar la red cuántica.


## Generación de resultados

Aquí viene todo lo relacionado a las pruebas que se realizaron en el Jupyter Notebook, donde los resultados se guardan en la carpeta `Results`.

### `PoC metrics.ipynb`

Esta es la implementación íntegra, se busca obtener la evolución de la fidelidad y el error de los qubits al no llegar algunos a destino, conforme aumenta el largo de la ruta. Además, se calcula el AUSE, dependiendo del largo de la ruta también.

### `Plot generation.ipynb`

Generar los gráficos de lo que se obtiene en `PoC metrics.ipynb`.

## Aplicaciones: Quantum Key Distribution (QKD)

Crypto es lo mejor del mundo.

En la carpeta `Quantum Key Distribution` se encuentra el Jupyter `QKD`, donde se reemplaza el `setup_datacollector` por uno más sofisticado, generando, además de la fidelidad, las mediciones del nodo inicial y el final, para así posteriormente generar una llave común, y luego encriptar un mensaje secreto. 

Me traspapelé un poco y las métricas de tiempo están aquí, deberían estar en el `PoC results`, pero bue. También, quise estudiar acerca del Secret Key Rate (SKR), pero no me fue muy bien.

Esta aplicación del simulador demuestra que está funcionando bien, porque efectivamente genera una llave común que permite cifrar y descifrar mensajes!

## Aplicaciones: Entangle-Retry Method (E-R Method)

Existe otra aplicación utilizando la base del `PoC results`. Lo que pasa es que, si el Entanglement Swapping falla, hay que reintentar todo. Sería mejor entrelazar cada nodo vecino, y hacer el Swapping cuando todos estén entrelazados primero. Por ejemplo, imaginemos la siguiente situación:

$$ A \rightarrow B \rightarrow C \rightarrow D$$

Lo que se hace originalmente es entrelazar $A$ con $B$, $B$ con $C$, y $C$ con $D$. Si la fidelidad resultante entre $A$ y $D$ es $0$, entonces hay que repetir el proceso. Puede que incluso el proceso haya fallado porque el entrelazamiento se hizo mal en un comienzo para un par de nodos.

La idea del `E-R Method` es entrelazar $A$ con $B$, $B$ con $C$, y $C$ con $D$, pero antes de hacer el Swapping, revisar si todos los entrelazamientos se hicieron bien. Si uno o varios fallan, sólo se reintentan esos! y ahí recién hacemos el Swapping.

Lo único que se ha hecho en esta línea es hacer el entrelazamiento inicial y retener los qubits que se hayan entrelazado correctamente. De ahí en adelante, la idea es hacer el Swapping "a mano", lo cual es más complicado por el momento.