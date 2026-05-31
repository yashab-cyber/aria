extends Control

# Configuration toggles
@export var transparent_background := false # Set to true if your OS compositor supports window transparency

# WebSocket connection variables
var socket := WebSocketPeer.new()
var ws_url := "ws://127.0.0.1:8000/ws/avatar"
var was_connected := false

# Animation states: "idle", "thinking", "analyzing", "speaking"
var current_state := "idle"

# Interpolation targets
var color_target := Color(0, 0.94, 1.0, 1.0) # Cyan for idle
var color_current := Color(0, 0.94, 1.0, 1.0)

var rot_speed_inner := 0.5
var rot_speed_outer := -0.3
var rot_speed_mid := 0.8

var rot_angle_inner := 0.0
var rot_angle_outer := 0.0
var rot_angle_mid := 0.0

var scale_target := 1.0
var scale_current := 1.0

# Soundwave simulation for speaking
var talk_wave_amplitude := 0.0

# Particles
var particles: Array = []

func _ready() -> void:
	# Enable transparent background rendering for viewport if requested
	get_viewport().transparent_bg = transparent_background
	if transparent_background:
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, true)
	else:
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, false)
	
	# Initialize particles
	for i in range(12):
		var p = {
			"angle": randf() * TAU,
			"speed": (0.2 + randf() * 0.8) * (1.0 if randf() > 0.5 else -1.0),
			"radius": 80.0 + randf() * 60.0,
			"size": 2.0 + randf() * 3.0,
			"alpha": 0.3 + randf() * 0.7
		}
		particles.append(p)
		
	# Attempt initial connection
	connect_to_server()

func connect_to_server() -> void:
	print("Connecting to A.R.I.A. Avatar Server at ", ws_url)
	socket.connect_to_url(ws_url)

func _process(delta: float) -> void:
	# Poll socket
	socket.poll()
	var ws_state = socket.get_ready_state()
	
	if ws_state == WebSocketPeer.STATE_OPEN:
		if not was_connected:
			print("Connected to A.R.I.A. server!")
			was_connected = true
			
		while socket.get_available_packet_count() > 0:
			var packet = socket.get_packet()
			var text = packet.get_string_from_utf8()
			var json = JSON.new()
			var error = json.parse(text)
			if error == OK:
				var data = json.get_data()
				if data is Dictionary and data.has("state"):
					set_agent_state(data["state"])
	else:
		if was_connected:
			print("Disconnected from server. Retrying...")
			was_connected = false
		if ws_state == WebSocketPeer.STATE_CLOSED:
			# Auto-reconnect after 3 seconds
			await get_tree().create_timer(3.0).timeout
			if socket.get_ready_state() == WebSocketPeer.STATE_CLOSED:
				connect_to_server()

	# State interpolation and animations
	update_state_animations(delta)
	queue_redraw()

func set_agent_state(new_state: String) -> void:
	if current_state == new_state:
		return
	current_state = new_state
	print("State changed to: ", current_state)
	
	match current_state:
		"idle":
			color_target = Color(0, 0.94, 1.0, 1.0) # Cyan
			rot_speed_inner = 0.5
			rot_speed_mid = -0.6
			rot_speed_outer = 0.3
			scale_target = 1.0
		"thinking":
			color_target = Color(1.0, 0.84, 0.0, 1.0) # Golden Yellow
			rot_speed_inner = 2.0
			rot_speed_mid = -2.5
			rot_speed_outer = 1.5
			scale_target = 1.1
		"analyzing":
			color_target = Color(1.0, 0.0, 0.92, 1.0) # Magenta/Purple
			rot_speed_inner = 4.0
			rot_speed_mid = -4.5
			rot_speed_outer = 3.0
			scale_target = 1.2
		"speaking":
			color_target = Color(0.0, 0.9, 0.46, 1.0) # Green/Teal
			rot_speed_inner = 1.0
			rot_speed_mid = -1.2
			rot_speed_outer = 0.8
			scale_target = 1.05

func update_state_animations(delta: float) -> void:
	# Lerp color and scale
	color_current = color_current.lerp(color_target, 5.0 * delta)
	scale_current = lerp(scale_current, scale_target, 5.0 * delta)
	
	# Update rotation angles
	rot_angle_inner += rot_speed_inner * delta
	rot_angle_mid += rot_speed_mid * delta
	rot_angle_outer += rot_speed_outer * delta
	
	# Speaking wave animation
	if current_state == "speaking":
		talk_wave_amplitude = lerp(talk_wave_amplitude, 1.0, 10.0 * delta)
	else:
		talk_wave_amplitude = lerp(talk_wave_amplitude, 0.0, 5.0 * delta)
		
	# Update particles
	for p in particles:
		var speed_mult = 1.0
		if current_state == "thinking":
			speed_mult = 2.5
		elif current_state == "analyzing":
			speed_mult = 4.0
		p["angle"] += p["speed"] * speed_mult * delta

func _draw() -> void:
	var screen_size = get_viewport_rect().size
	var center = screen_size / 2.0
	var base_radius := 60.0 * scale_current
	
	if not transparent_background:
		# Draw solid background color
		draw_rect(Rect2(Vector2.ZERO, screen_size), Color(0.02, 0.02, 0.05, 1.0))
		# Draw dynamic grid lines colored slightly by active state color
		var grid_spacing := 40.0
		for x in range(0, int(screen_size.x), int(grid_spacing)):
			draw_line(Vector2(x, 0), Vector2(x, screen_size.y), Color(color_current.r, color_current.g, color_current.b, 0.04))
		for y in range(0, int(screen_size.y), int(grid_spacing)):
			draw_line(Vector2(0, y), Vector2(screen_size.x, y), Color(color_current.r, color_current.g, color_current.b, 0.04))

	# Draw background circle glow
	draw_circle(center, base_radius + 40, Color(color_current.r, color_current.g, color_current.b, 0.03))
	draw_circle(center, base_radius + 20, Color(color_current.r, color_current.g, color_current.b, 0.06))
	
	# Draw core (pulsing)
	var time_sec = Time.get_ticks_msec() / 1000.0
	var pulse := sin(time_sec * (8.0 if current_state == "thinking" else 3.0)) * 4.0
	
	if current_state == "speaking":
		# React to simulated voice frequency
		pulse = sin(time_sec * 25.0) * 12.0 * talk_wave_amplitude
		
	var core_radius = (base_radius * 0.4) + pulse
	draw_circle(center, core_radius, color_current)
	draw_circle(center, core_radius * 0.6, Color(1, 1, 1, 0.8)) # bright center core
	
	# Draw Middle Ring (dashed / segments)
	var mid_radius = base_radius * 0.8
	var segment_count := 12
	var segment_angle := TAU / segment_count
	var gap_ratio := 0.4 # percentage of gap
	
	for i in range(segment_count):
		var start_a = (i * segment_angle) + rot_angle_mid
		var end_a = start_a + (segment_angle * (1.0 - gap_ratio))
		draw_arc(center, mid_radius, start_a, end_a, 16, color_current, 2.0, true)
		
	# Draw Outer Ring (dotted or scanning lines)
	var outer_radius = base_radius * 1.2
	if current_state == "analyzing":
		# Draw horizontal scanning bar across the face of the core
		var scan_y = center.y + sin(time_sec * 6.0) * base_radius
		draw_line(Vector2(center.x - base_radius, scan_y), Vector2(center.x + base_radius, scan_y), color_current, 2.0)
		draw_line(Vector2(center.x - base_radius * 0.8, scan_y - 2), Vector2(center.x + base_radius * 0.8, scan_y - 2), Color(1, 1, 1, 0.3), 1.0)
		
		# Draw square frame targets
		var size_f = base_radius * 1.3
		draw_rect(Rect2(center.x - size_f, center.y - size_f, size_f * 2, size_f * 2), color_current, false, 1.5)
	else:
		# Draw simple dotted outer ring
		var dot_count := 24
		for i in range(dot_count):
			var a = (i * (TAU / dot_count)) + rot_angle_outer
			var dot_pos = center + Vector2(cos(a), sin(a)) * outer_radius
			draw_circle(dot_pos, 2.0, color_current)
			
	# Draw orbit particles
	for p in particles:
		var rad = p["radius"] * scale_current
		var pos = center + Vector2(cos(p["angle"]), sin(p["angle"])) * rad
		var col = color_current
		col.a = p["alpha"]
		draw_circle(pos, p["size"], col)
