# ![Blender GameRig](img/logo.jpg "Logo")

*Read this in other languages: [English](README.md), [日本語](README.ja.md).*

## Rigging Add-on for Blender 2.80

Rigging framework for game / realtime content development. Hard fork from [Rigify](https://archive.blender.org/wiki/index.php/Extensions:2.6/Py/Scripts/Rigging/Rigify/) (official add-on).

<!-- TOC -->

- [How to use](#how-to-use)
  - [Install GameRig to your blender](#install-gamerig-to-your-blender)
  - [Add 'metarig'](#add-metarig)
  - [Adjust metarig](#adjust-metarig)
    - [Add additional bones](#add-additional-bones)
  - [Generate rig](#generate-rig)
  - [Regenerate rig](#regenerate-rig)
- [Deference from Rigify](#deference-from-rigify)
  - [Clean hierarchy](#clean-hierarchy)
  - [Multi Face Rig](#multi-face-rig)
  - [Blend animation and physic simulation result](#blend-animation-and-physic-simulation-result)
- [Tips](#tips)
  - [How to use with an existing armature](#how-to-use-with-an-existing-armature)
  - [Why 'Unity Mechanim/Human' metarig has X 90° rotation](#why-unity-mechanimhuman-metarig-has-x-90-rotation)

<!-- /TOC -->

## How to use

### Install GameRig to your blender

Download zip file for install from [Releases Page](https://github.com/SAM-tak/BlenderGameRig/releases).

![download link](img/downloadlink.jpg "download link")

Back to Blender and open Preference Window, and click 'Install...' button.

![addonpanel](img/addonpanel.jpg "addonpanel")

Choose downloaded zip file and click 'Install add-on from File...' button.

![installaddon](img/installaddon.jpg "installaddon")

Then GameRig will be found in Add-on list (filtering by categoly 'Rigging', you can find faster), click check box to activate.

![addedaddon](img/addedaddon.jpg "addedaddon")

### Add 'metarig'

> Mode: Object Mode
>
> Hotkey: ⇧ A
>
> Menu: Add → Add Armature

![add metarig menu](img/addmetarig.jpg "add metarig menu")

![added metarig](img/metarig.jpg "added metarig")

### Adjust metarig

Edit metarig armature, let it fit to your character mesh.

![adjusted metarig](img/adjustmetarig.jpg "adjusted metarig")

Set vertex group for armature deforming.

GameRig will copy bones without renaming differs from 'rigify', you can test armature deforming with metarig armature.

![setup vertexgroup](img/setupvertexgroup.jpg "setup vertexgroup")

#### Add additional bones

If your model has hair / cloth / etc. bones, add these too.

These bones will be copied to generated rig.

If they have constraints and/or have drivers, these will be copied too with right target.

![final metarig](img/finalmetarig.jpg "final metarig")

### Generate rig

When you are ready, click 'Generate New Rig' Button of Armature Properties tab.

![armature panel](img/armaturepanel.jpg "armature panel")

Done.

![generated rig](img/generatedrig.jpg "generated rig")

Parent mesh objects to rig armature.

![parenting](img/parenting.jpg "parenting")

In pose mode, you can make pose or animation with generated rig featuring IK/FK blending, etc.

![posing](img/posing.jpg "posing")

Rig's special parameters and functions will be available in 'GameRig Properties' panel that be placed on Item tab of Sidebar.

![properties](img/properties.jpg "properties")

### Regenerate rig

If you feel some bones have bad positions, it means you need to edit metarig again, but you can regenerate rig quickly after edit metarig.

Edit metarig again, and click 'Regenerate rig' button to apply changes.

![regenerate](img/regenerate.jpg "regenerate")
> Note:
>
> Please confirm current collection contains target rig to overwrite.
>
> Otherwise, gamerig generate a new rig to current active collection.
>
> ![wrong collection](img/wrongcollection.jpg "wrong collection")

## Deference from Rigify

### Clean hierarchy

GameRig dosen't rename original bones and dosen't add deform bone and dosen't insert any bones to original bone tree.

More suitable for game / VR content development.

![unity mechanim avatar](img/unitymechanimavatar.jpg "unity mechanim avatar")

### Multi Face Rig

More flexible face rig.

![multihead metarig](img/multiheadmetarig.jpg "multihead metarig")
![multihead rig](img/multiheadrig.jpg "multihead rig")

### Blend animation and physic simulation result

**'generic'** and **'tentacle'** rig can blend between own result and metabone's constraint result if metabone have constraint.

![rigphysicsblend](img/rigphysicsblend.gif "rigphysicsblend")

## Tips

### How to use with an existing armature

An armature not recognized as GameRig's metarig, the armature's properties panel has no GameRig panel.

Then you cannot setup metarig with existing armature.

![no gamerig panel](img/nogamerigpanel.jpg "no gamerig panel")

In this case, **add 'Single Bone' metarig** and **join (Ctrl + J / Menu Object→Join) an existing armature to it**. And remove 'root' bone from metarig if you don't need it.

![add single bone](img/addsinglebone.jpg "add single bone")

Gamerig panel will be available in armature properties panel.

![joined armature](img/joinedarmature.jpg "joined armature")

In pose mode, you can set rig parameter in GameRig Rig Type panel that be placed on bone properties tab.

![edit rig type](img/editrigtype.jpg "edit rig type")

### Why 'Unity Mechanim/Human' metarig has X 90° rotation

By deference of coordinate system between Blender and Unity, imported mesh lie down in Unity with a fbx file exported by Blender. This is a reason of metarig has X +90° rotation (GameRig generates a rig with same rotation as metarig).

![imported fbx 1](img/importedfbx1.jpg "imported meshes lie down")

Rig armature having X +90° rotation and their children having X -90° rotation, and settings of export fbx are:

- scale is 0.01
- 'Apply Unit' is off
- 'Apply Transform' is on

and Unity side import settings are:

- Scale is 1.0
- 'Convert Unit' is off

![parent has x +90° rotation](img/parentrotation.jpg "x +90° rotation")
![child has x -90° rotation](img/childrotation.jpg "x -90° rotation")
![export setting](img/exportsetting.jpg "export setting")
![import setting](img/importsetting.jpg "import setting")

These settings make imported fbx object having right orientation and clean transform (no rotation, no scaling) on Unity.

> Note:
>
> For combination of Blender 2.80 and Unity 2019.1
>
> I was using deferent settings for same effect in Blender 2.79 and Unity 2018.4 era.

![no rotation and no scale](img/cleantransform.gif "no rotation and no scale")

## LICENSE

[GNU GENERAL PUBLIC LICENSE](LICENSE)
