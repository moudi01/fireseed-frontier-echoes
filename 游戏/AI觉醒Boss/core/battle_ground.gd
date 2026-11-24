extends Node3D
const ART=preload("res://core/forest_art.gd")
## Authored framing outside the legal 10x8 cells; no collision/navigation authority.
func _ready():
	var soil=MeshInstance3D.new();var plane=PlaneMesh.new();plane.size=Vector2(100,100);soil.mesh=plane;soil.material_override=ART.earth();soil.position.y=-.075;add_child(soil)
	# Back/left canopy frames a gap toward the continuing road. Foreground stays open.
	var trees=[[-10,-8,1.2],[-7.8,-7,1.05],[-5.4,-8.8,1.2],[-2.7,-8,1.05],[1.0,-10,1.0],[5.2,-8.3,1.1],[8.4,-9.8,1.2],[-9,-3.6,1.0],[-8.4,.6,.9],[-10,4.5,.8],[10,-4.5,.7],[11,0,.65]]
	for i in range(trees.size()):
		var t=trees[i];ART.tree(self,Vector3(t[0],0,t[1]),t[2],i)
	var groups=[Vector3(-6.2,0,-3.1),Vector3(-6.8,0,.1),Vector3(-6.3,0,3.2),Vector3(6.7,0,-3.8),Vector3(6.9,0,.2),Vector3(7.1,0,3.1)]
	for i in range(groups.size()):
		ART.rock(self,groups[i],i)
		ART.shrub(self,groups[i]+Vector3(.65,0,-.25),i)
		if i%2==0:ART.shrub(self,groups[i]+Vector3(-.5,0,.35),i+2)
	ART.rod(self,Vector3(-7.3,.06,5.6),Vector3(-5.8,.02,5.1),.10)
	ART.rock(self,Vector3(5.9,-.05,5.9),2)
