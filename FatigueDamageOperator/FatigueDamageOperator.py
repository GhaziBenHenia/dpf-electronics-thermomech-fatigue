from ansys.dpf import core as dpf
from ansys.dpf.core.custom_operator import CustomOperatorBase, record_operator
from ansys.dpf.core.operator_specification import CustomSpecification, SpecificationProperties, PinSpecification
import numpy as np
from scipy.special import gamma

class FatigueDamageOperator(CustomOperatorBase):

    @property
    def name(self):
        return "fatigue_damage_operator"

    @property
    def specification(self) -> CustomSpecification:
        spec = CustomSpecification()
        spec.description = """Computes accumulated damage using:
        1. Coffin-Manson fatigue model
        2. Arrhenius-based degradation
        3. Weibull failure probability"""

        # Input pins
        spec.inputs = {
            0: PinSpecification("temperature_fields", [dpf.FieldsContainer], 
                              "Input temperature fields container", True),
            1: PinSpecification("gradient_fields", [dpf.FieldsContainer], 
                              "Input thermal gradient fields container", True),
            2: PinSpecification("material_map", [dict], 
                              "Material properties dictionary", True)
        }

        # Output pins
        spec.outputs = {
            0: PinSpecification("damage_container", [dpf.FieldsContainer], 
                              "Output damage fields container")
        }

        spec.properties = SpecificationProperties(category="fatigue_analysis")
        return spec

    def run(self):
        # Get inputs
        temp_fields = self.get_input(0, dpf.FieldsContainer)
        grad_fields = self.get_input(1, dpf.FieldsContainer)
        material_map = self.get_input(2, dict)

        # Call the damage calculation function
        damage_container = calculate_fatigue_damage(temp_fields, grad_fields, material_map)

        # Set output
        self.set_output(0, damage_container)
        self.set_succeeded()

def calculate_fatigue_damage(temp_fields, grad_fields, material_map):
    """
    Computes accumulated damage using:
    1. Coffin-Manson fatigue model
    2. Arrhenius-based degradation
    3. Weibull failure probability
    """
    damage_container = dpf.FieldsContainer()
    
    for t in range(len(temp_fields)):
        temp_data = temp_fields[t].data
        grad_data = grad_fields[t].data
        
        delta_temp = temp_data.max() - temp_data.min()
        grad_magnitude = np.linalg.norm(grad_data, axis=1)
        
        damage_field = dpf.Field()
        damage_values = []
        
        for i, (T, grad) in enumerate(zip(temp_data, grad_magnitude)):
            mat_props = material_map[temp_fields[t].scoping.id(i)]
            
            # Coffin-Manson equation
            plastic_strain = mat_props['alpha'] * delta_temp
            cycles_to_failure = (mat_props['C'] / plastic_strain)**(1/mat_props['m'])
            
            # Arrhenius degradation
            degradation = np.exp(-mat_props['Ea']/(8.617e-5 * T.mean()))
            
            # Weibull failure probability
            beta = mat_props['weibull_beta']
            eta = mat_props['weibull_eta'] * degradation
            failure_prob = 1 - np.exp(-(cycles_to_failure/eta)**beta)
            
            # Combined damage metric
            damage = (failure_prob * grad * 
                     mat_props['stress_sensitivity'])
            damage_values.append(damage)
        
        damage_field.data = damage_values
        damage_field.scoping = temp_fields[t].scoping
        damage_container.add_field({"damage": damage_field}, 
                                  label_space={"time": t})
    
    return damage_container

def load_operators(*args):
    record_operator(FatigueDamageOperator, *args)