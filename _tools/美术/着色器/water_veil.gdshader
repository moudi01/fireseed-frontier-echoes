shader_type spatial;
render_mode unshaded,cull_disabled,depth_draw_never;
#include "res://art/water_surface.gdshaderinc"
uniform vec3 lamp;
uniform vec3 side_lamp;
uniform float side_power;
uniform float explored_front;
uniform float time_clock;
uniform float borrow_time;
uniform float obstruction;
uniform float side_flash;
uniform float art_time;
uniform vec2 pocket_center;
uniform vec2 pocket_radius;
varying vec3 world;
void vertex() { world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz; }
void fragment() {
	float r=length((world.xz-pocket_center)/pocket_radius);
	if(r>=1.0) { discard; }
	ALBEDO=water_r2_surface(world,lamp,art_time);
	ALPHA=water_r2_coverage(world,art_time,r);
}
