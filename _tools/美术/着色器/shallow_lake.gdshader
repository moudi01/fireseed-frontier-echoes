shader_type spatial;
render_mode unshaded,cull_disabled;
#include "res://art/shallow_field.gdshaderinc"
uniform vec3 lamp;
uniform float explored_front;
uniform float art_time;
uniform float kind=1.0;
varying vec3 world;
void vertex(){world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
	if(shallow_domain(world.xz)<0.0){discard;}
	float known=(1.0-smoothstep(explored_front-0.25,explored_front+0.25,world.x))*(1.0-smoothstep(2.2,3.6,abs(world.z)))*step(-15.0,world.x);
	ALBEDO=shallow_water(world,lamp,art_time,known);
}
