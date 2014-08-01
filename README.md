ice
===

Code for the ISEE-3 Reboot Mission

[Balint Seeber](http://spench.net) ([Twitter](http://twitter.com/spenchdotnet))

[https://github.com/balint256/ice](https://github.com/balint256/ice)

## tlm

Telemetry parser, decoder, server & grapher.

### Pre-reqs

* python, and bindings for:
 * curses
 * json-pickle
 * matplotlib (for grapher)

### Features

* Multiple raw stream inputs:
 * Listen on UDP socket for hard-decision symbols
 * Connect to TCP server supplying decoded full frames
 * Input from file
* Elements are declared in `elems_*.py` (the engine does the rest in terms of collecting the data)
* Elements built using extensible primitives:
 * CustomOffset: collection of raw bytes/bits
 * Parser: assemble raw bytes/bits into element data
 * Validator: check if data is valid
 * Formatter: convert data into human-readable form
* Element and curve files are automatically loaded
* Automatically creates UI layouts, or customise them yourself
* Headless operation
* In-built JSON server

### UI

The UI is displayed using curses. It will only work if your terminal is large enough!

Keyboard shortcuts (shown in top-right corner underneath current layout name):

	`		Raw frames
	~		Subcom frames
	1 to 0	Automatically mapped to layouts
	h		History layout
	<other>	First letter of layout name (see below)
	<ESC>	Quit

Custom layouts can be created in `layouts.py`.
If no custom layout is specified, layouts will be automatically generated (one for each `elems_*.py`).
An automatically-generated layout will assume the name of the element definition file (i.e. `elems_<name>.py`).

### Server

In-built JSON server (`server.py`) allows client applications (e.g. `tlm_grapher.py`) to register for updates to elements.
The server will push updates whenever a registered element's value is updated (the value may or may not have changed).
See the client code in `tlm_graph.py` for an example of the protocol.

### Usage

	Usage: tlm.py: [options] [TCP server[:port]]

	Options:
	  -h, --help            show this help message and exit
	  -L LOAD_PATH, --load-path=LOAD_PATH
							path to load elements from [default=.]
	  -s SLEEP, --sleep=SLEEP
							loop sleep time (s) [default=0.01]
	  -p PORT, --port=PORT  port (UDP server or TCP client) [default=22222]
	  -P SERVER_PORT, --server-port=SERVER_PORT
							server port [default=21012]
	  -S, --always-sleep    always sleep in inner loop [default=False]
	  -v, --verbose         verbose logging outside of UI [default=False]
	  -m MODE, --mode=MODE  select telemetry mode (science,engineering)
							[default=engineering]
	  -H, --headless        do not run the UI [default=False]
	  -i INPUT, --input=INPUT
							input file (instead of network) [default=none]

	Usage: tlm_graph.py: [options] <destination>[:port] <element>[,<key=value>]... ...

	Options:
	  -h, --help            show this help message and exit
	  -p PORT, --port=PORT  TCP port [default=21012]
	  -s SLEEP, --sleep=SLEEP
							reconnect sleep time (s) [default=1.0]
	  -T TIMEOUT, --timeout=TIMEOUT
							GUI event handler timeout (s) [default=0.01]
	  -d DURATION, --duration=DURATION
							default duration (s) [default=60.0]
	  -t TYPE, --type=TYPE  default value type (raw, out) [default=out]
	  -x X_TYPE, --x-type=X_TYPE
							default X-axis type (blank: consecutive samples, time)
							[default=]
	  -n, --no-reconnect    do not automatically reconnect [default=False]

### Examples

`./tlm.py -m s server:12321`

Connects to port 12321 on server and starts up in science mode.

`./tlm_graph.py localhost accelerometer,duration=1000 28v_bus shunt_dump_current fss_angle_a`

Connects to the local running instance of tlm.py and graphs accelerometer values over a longer duration, as well as the other three elements over the default duration.
