from PySide2 import QtCore, QtWidgets
import maya.cmds as cmds
import System.utils as utils
import importlib
importlib.reload(utils)


class MirrorModule(QtWidgets.QDialog):
    def __init__(self):
        super(MirrorModule, self).__init__()
        selection = cmds.ls(sl=1, tr=1)
        if len(selection) == 0:
            return
        
        first_selected = selection[0]
        
        self.modules = []
        self.group = None
        if first_selected.find("Group__") == 0:
            self.modules = self.find_sub_modules(first_selected)
            self.group = first_selected
        else:
            module_namespace_info = utils.strip_leading_namespace(first_selected)
            self.modules.append(module_namespace_info[0])
            
        temp_module_list = []
        for module in self.modules:
            if self.is_module_a_mirror(module):
                QtWidgets.QMessageBox.critical(self, "Error", "Cannot mirror a previously mirrored module, aborting mirror.")
                return
            
            if not self.can_module_be_mirrored(module):
                print(f"Module: {module} is of a module type that cannot be mirrored... skipping module.")
            else:
                temp_module_list.append(module)
        self.modules = temp_module_list
        
        if len(self.modules) > 0:
            self.mirror_module_UI()
            
    def find_sub_modules(self, group):
        return_modules = []
        
        children = cmds.listRelatives(group, c=1)
        children = cmds.ls(children, tr=1)
        
        for child in children:
            if child.find("Group__") == 0:
                return_modules.extend(self.find_sub_modules(child))
            else:
                namespace_info = utils.strip_leading_namespace(child)
                if namespace_info is not None and namespace_info[1] == "module_transform":
                    module = namespace_info[0]
                    return_modules.append(module)
                    
        return return_modules
    
    def is_module_a_mirror(self, module):
        module_group = f"{module}:module_grp"
        return cmds.attributeQuery("mirrorLinks", n=module_group, ex=1)
    
    def can_module_be_mirrored(self, module):
        module_name_info = utils.find_all_module_names("/Modules/Blueprint")
        valid_modules = module_name_info[0]
        valid_module_names = module_name_info[1]
        
        module_name = module.partition("__")[0]
        
        if module_name not in valid_module_names:
            return False
        
        index = valid_module_names.index(module_name)
        mod = __import__(f"Blueprint.{valid_modules[index]}", {}, {}, valid_modules[index])
        importlib.reload(mod)
        
        ModuleClass = getattr(mod, mod.CLASS_NAME)
        module_inst = ModuleClass("null", None)
        
        return module_inst.can_module_be_mirrored()
    
    def mirror_module_UI(self):
        self.module_names = []
        for module in self.modules:
            self.module_names.append(module.partition("__")[2])
        self.same_mirror_settings_for_all = False
        
        if len(self.modules) > 1:
            result = cmds.confirmDialog(title="Mirror Multiple Module", message=f"{str(len(self.modules))} modules selected for mirror.\nHow would you like to apply mirror settings?", b=["Same for all", "Individually", "Cancel"], db="Same for all", cb="Cancel", ds="Cancel")
            
            if result == "Cancel":
                return
            elif result == "Same for all":
                self.same_mirror_settings_for_all = True
        
        self.UI_elements = {}
        
        if cmds.window("mirror_module_UI_window", exists=True):
            cmds.deleteUI("mirror_module_UI_window")
        
        window_width = 350
        window_height = 450
        scroll_width = window_width - 30

        mirror_plane_text_width = 80
        mirror_plane_radio_width = (scroll_width - mirror_plane_text_width) / 3

        self.UI_elements['window'] = cmds.window("mirror_module_UI_window", w=window_width, h=window_height, t="Mirror Module(s)", s=0)
        self.UI_elements['scroll_layout'] = cmds.scrollLayout(hst=0)
        self.UI_elements['top_column_layout'] = cmds.columnLayout(adj=1, rs=3)

        # Create mirror plane options
        self.UI_elements['mirror_plane_row_column'] = cmds.rowColumnLayout(
            nc=4, 
            cat=[(1, "right", 0), (2, "both", 0), (3, "both", 0), (4, "both", 0)], 
            cw=[
                (1, mirror_plane_text_width), 
                (2, mirror_plane_radio_width), 
                (3, mirror_plane_radio_width), 
                (4, mirror_plane_radio_width)
            ]
        )

        cmds.text(l="Mirror Plane: ")
        self.UI_elements["mirror_plane_radio_collection"] = cmds.radioCollection()
        cmds.radioButton("XY", l="XY", sl=0)
        cmds.radioButton("YZ", l="YZ", sl=1)
        cmds.radioButton("XZ", l="XZ", sl=0)

        cmds.setParent(self.UI_elements['top_column_layout'])
        cmds.separator()
        cmds.text(l="Mirrored Name(s):")
        
        column_width = scroll_width / 2
        self.UI_elements['module_name_row_column'] = cmds.rowColumnLayout(nc=2, cat=(1, "right", 0), cw=[(1, column_width), (2, column_width)])
        for module in self.module_names:
            cmds.text(l=f"{module} >> ")
            self.UI_elements["moduleName_" + module] = cmds.textField(en=1, tx=f"{module}_mirror")
        
        cmds.setParent(self.UI_elements['top_column_layout'])
        cmds.separator()
        
        if self.same_mirror_settings_for_all:
            self.generate_mirror_function_controls(None, scroll_width)
        else:
            for module in self.module_names:
                self.generate_mirror_function_controls(module, scroll_width)
        
        cmds.setParent(self.UI_elements['top_column_layout'])
        cmds.separator()
        
        self.UI_elements['button_row'] = cmds.rowLayout(nc=2, cw=[(1, column_width), (2, column_width)], cat=[(1, 'both', 10), (2, 'both', 10)], cal=[(1, 'center'), (2, 'center')])
        cmds.button(l="Accept", c=self.accept_window) 
        cmds.button(l="Cancel", c=self.cancel_window)
                
        cmds.showWindow(self.UI_elements['window'])
        
    def generate_mirror_function_controls(self, module_name, scroll_width):
        rotation_radio_collection = 'rotation_radioCollection_all'
        translation_radio_collection = 'translation_radioCollection_all'
        text_label = 'Mirror Setting:'
        
        behavior_name = 'behavior__'
        orientation_name = 'orientation__'
        mirrored_name = 'mirrored__'
        world_space_name = 'world_space__'
        
        if module_name is not None:
            rotation_radio_collection = f"rotation_radioCollection_{module_name}"
            translation_radio_collection = f"translation_radioCollection_{module_name}"
            text_label = f"{module_name} Mirror Settings:"
            
            behavior_name = f"behavior__{module_name}"
            orientation_name = f'orientation__{module_name}'
            mirrored_name = f'mirrored__{module_name}'
            world_space_name = f'world_space__{module_name}'
        
        cmds.text(l=text_label)
        
        form = cmds.formLayout()
        
        # Rotation Mirror Function
        rotation_label = cmds.text(l="Rotation Mirror Function: ", align='left')
        self.UI_elements[rotation_radio_collection] = cmds.radioCollection()
        behavior_radio = cmds.radioButton(behavior_name, l="Behavior", sl=1)
        orientation_radio = cmds.radioButton(orientation_name, l="Orientation", sl=0)
        
        cmds.formLayout(form, edit=True,
            attachForm=[
                (rotation_label, 'top', 0), 
                (rotation_label, 'left', 6)
            ],
            attachControl=[
                (behavior_radio, 'left', 20, rotation_label),
                (orientation_radio, 'left', 5, behavior_radio)
            ],
            attachPosition=[
                (behavior_radio, 'top', 0, 0),  # Top at 25% height
                (orientation_radio, 'top', 0, 0)  # Top at 25% height
            ]
        )
        
        # Translation Mirror Function
        translation_label = cmds.text(l="Translation Mirror Function: ", align='left')
        self.UI_elements[translation_radio_collection] = cmds.radioCollection()
        mirrored_radio = cmds.radioButton(mirrored_name, l="Mirrored", sl=1)
        world_space_radio = cmds.radioButton(world_space_name, l="World Space", sl=0)
        
        cmds.formLayout(form, edit=True,
            attachForm=[
                (translation_label, 'left', 5)
            ],
            attachControl=[
                (mirrored_radio, 'left', 5, translation_label),
                (world_space_radio, 'left', 5, mirrored_radio)
            ],
            attachPosition=[
                (translation_label, 'top', 0, 50),  # Top at 50% height
                (mirrored_radio, 'top', 0, 50),  # Top at 50% height
                (world_space_radio, 'top', 0, 50)  # Top at 50% height
            ]
        )
        
        cmds.setParent(self.UI_elements['top_column_layout'])
        cmds.text(l='')
    
    def cancel_window(self, *args):
        cmds.deleteUI(self.UI_elements['window'])
        
    def accept_window(self, *args):
        self.module_info = []
        self.mirror_plane = cmds.radioCollection(self.UI_elements["mirror_plane_radio_collection"], q=1, sl=1)
        
        for i in range(len(self.modules)):
            original_module = self.modules[i]
            original_module_name = self.module_names[i]
            
            original_module_prefix = original_module.partition("__")[0]
            mirror_module_user_specified_name = cmds.textField(self.UI_elements[f'moduleName_{original_module_name}'], q=1, tx=1)
            mirrored_module_name = f"{original_module_prefix}__{mirror_module_user_specified_name}"
            
            if utils.does_user_specified_name_exist(mirror_module_user_specified_name):
                cmds.confirmDialog(t="Name Conflict", message=f"Name: {mirror_module_user_specified_name} \nalready exists, aborting out of mirror.", b=["Accept"], db="Accept")
                return
            rotation_function = ''
            translation_function = ''
            
            if self.same_mirror_settings_for_all == True:
                rotation_function = cmds.radioCollection(self.UI_elements["rotation_radioCollection_all"], q=1, sl=1)
                translation_function = cmds.radioCollection(self.UI_elements["translation_radioCollection_all"], q=1, sl=1)
            else:
                rotation_function = cmds.radioCollection(self.UI_elements[f"rotation_radioCollection_{original_module_name}"], q=1, sl=1)
                translation_function = cmds.radioCollection(self.UI_elements[f"translation_radioCollection_{original_module_name}"], q=1, sl=1)
            
            rotation_function = rotation_function.partition("__")[0] 
            translation_function = translation_function.partition("__")[0] 
            
            self.module_info.append([original_module, mirrored_module_name, self.mirror_plane, rotation_function, translation_function])
            
        cmds.deleteUI(self.UI_elements['window'])
        self.mirror_modules()
        
 




    def mirror_modules(self):
        mirror_module_progress_UI = cmds.progressWindow(t="Mirroring Module(s)", st="This may take a few minutes", ii=0)
        mirror_module_progress = 0
        
        mirror_modules_progress_stage1_proportion = 15
        mirror_modules_progress_stage2_proportion = 70
        mirror_modules_progress_stage3_proportion = 10
        
        module_name_info = utils.find_all_module_names("/Modules/Blueprint")
        valid_modules = module_name_info[0]
        valid_module_names = module_name_info[1]
        
        for module in self.module_info:
            module_name = module[0].partition("__")[0]
            
            if module_name in valid_module_names:
                index = valid_module_names.index(module_name)
                module.append(valid_modules[index])
                
        mirror_module_progress_increment = mirror_modules_progress_stage1_proportion/len(self.module_info)
        for module in self.module_info:
            user_specified_name = module[0].partition("__")[2]
            mod = __import__(f"Blueprint.{module[5]}", {}, {}, [module[5]])
            importlib.reload(mod)
            
            ModuleClass = getattr(mod, mod.CLASS_NAME)
            module_inst = ModuleClass(user_specified_name, None)
            
            hook_object = module_inst.find_hook_object()
            new_hook_object = None
            hook_module = utils.strip_leading_namespace(hook_object)[0]
            hook_found = False
            
            for m in self.module_info:
                if hook_module == m[0]:
                    hook_found = True
                    
                    if m == module:
                        continue
                    
                    hook_object_name = utils.strip_leading_namespace(hook_object)[1]
                    new_hook_object = f"{m[1]}:{hook_object_name}"
            
            if not hook_found:
                new_hook_object = hook_object
                
            module.append(new_hook_object)
            
            hook_constrained = module_inst.is_root_constrained()
            module.append(hook_constrained)
            mirror_module_progress += mirror_module_progress_increment
            cmds.progressWindow(mirror_module_progress_UI, e=1, pr=mirror_module_progress)
            
        mirror_module_progress_increment = mirror_modules_progress_stage2_proportion / len(self.module_info)
        for module in self.module_info:
            new_user_specified_name = module[1].partition("__")[2]
            mod = __import__(f"Blueprint.{module[5]}", {}, {}, [module[5]])
            importlib.reload(mod)
            
            ModuleClass = getattr(mod, mod.CLASS_NAME)
            module_inst = ModuleClass(new_user_specified_name, None)
            
            module_inst.mirror(module[0], module[2], module[3], module[4])
            mirror_module_progress += mirror_module_progress_increment
            cmds.progressWindow(mirror_module_progress_UI, e=1, pr= mirror_module_progress)
            
        mirror_module_progress_increment = mirror_modules_progress_stage3_proportion/len(self.module_info)
        
        for module in self.module_info:
            new_user_specified_name = module[1].partition("__")[2]
            mod = __import__(f"Blueprint.{module[5]}", {}, {}, [module[5]])
            importlib.reload(mod)
            
            ModuleClass = getattr(mod, mod.CLASS_NAME)
            module_inst = ModuleClass(new_user_specified_name, None)

            module_inst.rehook(module[6])
            
            if hook_constrained:
                module_inst.constrain_root_to_hook()
                
            mirror_module_progress += mirror_module_progress_increment
            cmds.progressWindow(mirror_module_progress_UI, e=1, pr=mirror_module_progress)
        
        if self.group is not None:
            print(f"======> {self.group}")
            cmds.lockNode("Group_container", l=0, lu=0)
            
            group_parent = cmds.listRelatives(self.group, p=1)
            
            if group_parent is not None:
                group_parent = group_parent[0]
                
            self.process_group(self.group, group_parent)
            
            cmds.lockNode("Group_container", l=1, lu=1)
            cmds.select(cl=1)  
        
        cmds.progressWindow(mirror_module_progress_UI, e=1, ep=1)
        utils.force_scene_update()
        
    def process_group(self, group, parent):
        import System.GroupSelected as groupSelected
        importlib.reload(groupSelected)
        
        temp_group = cmds.duplicate(group, po=1, ic=1)[0]
        empty_group = cmds.group(em=1)
        cmds.parent(temp_group, empty_group, a=1)
        
        scale_axis = ".scaleX"
        
        if self.mirror_plane == "XZ":
            scale_axis = ".scaleY"
        elif self.mirror_plane == "XY":
            scale_axis = ".scaleZ"
        
        cmds.setAttr(f"{empty_group}{scale_axis}", -1)
        
        # Create an instance of GroupSelected
        group_selected_instance = groupSelected.GroupSelected()
        
        # Pass the instance to GroupUI
        instance = groupSelected.GroupUI(group_selected_instance)
       
        group_suffix = group.partition("__")[2]
        new_group = instance.create_group_at_specified(f"{group_suffix}_mirror", temp_group, parent)
        
        cmds.lockNode("Group_container", l=0, lu=1)
