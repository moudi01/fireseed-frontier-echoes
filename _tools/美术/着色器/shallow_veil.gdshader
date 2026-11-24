shader_type spatial;
render_mode unshaded,cull_disabled,depth_draw_never;
#include "res://art/shallow_field.gdshaderinc"
uniform vec3 lamp;
uniform float explored_front;
uniform float art_time;
varying vec3 world;
void vertex(){world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
	float boundary=shallow_domain(world.xz);
	if(boundary>=0.0){discard;}
	float known=(1.0-smoothstep(explored_front-0.25,explored_front+0.25,world.x))*(1.0-smoothstep(2.2,3.6,abs(world.z)))*step(-15.0,world.x);
	ALBEDO=shallow_water(world,lamp,art_time,known);
	// Shared modest coverage, no r2 bottom absorption; meet opaque water at the edge.
	ALPHA=mix(0.16,1.0,smoothstep(-0.20,0.0,boundary));
}
