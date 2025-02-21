from ansys.dpf import core as dpf
from ansys.dpf.core import operators as ops

# ==================================================================
# Workflow Implementation
# ==================================================================
model = dpf.Model(r"D:\ElectronicsData\advanced_package.rst")
streams = model.metadata.streams_provider
mesh = model.metadata.meshed_region

# Material properties database
material_params = {
    1: {  # Silicon
        'alpha': 2.6e-6,
        'C': 0.026,
        'm': 0.12,
        'Ea': 0.7,
        'weibull_beta': 2.3,
        'weibull_eta': 1e6,
        'stress_sensitivity': 0.85
    },
    2: {  # Solder
        'alpha': 21e-6,
        'C': 0.33,
        'm': 0.18,
        'Ea': 0.5,
        'weibull_beta': 1.8,
        'weibull_eta': 5e5,
        'stress_sensitivity': 1.2
    }
}

time_scoping = ops.utility.time_freq_scoping_fc(time_ids=list(range(1,11)))
temp_op = ops.result.temperature(time_scoping=time_scoping)
grad_op = ops.invariant.thermal_gradient()
split_mat = ops.mesh.split_mesh(property="material")

grad_op.inputs.temperature.connect(temp_op.outputs.fields_container)
split_mat.inputs.mesh.connect(mesh)

# Instantiate and connect custom operator
damage_op = dpf.Operator("FatigueDamageOperator")
damage_op.inputs.temperature_fields.connect(temp_op.outputs.fields_container)
damage_op.inputs.gradient_fields.connect(grad_op.outputs.fields_container)
damage_op.inputs.material_map.connect(material_params)

threshold_op = ops.logic.threshold()
threshold_op.inputs.field.connect(damage_op.outputs.damage_container)
threshold_op.inputs.threshold.connect(0.8)  # Critical damage level

rescope_ops = {}
for mat_id in material_params.keys():
    rescope = ops.scoping.rescope_fc()
    mat_scope = dpf.Scoping(location="elemental", ids=[mat_id])
    rescope.inputs.mesh_scoping.connect(mat_scope)
    rescope.inputs.fields_container.connect(damage_op.outputs.damage_container)
    rescope_ops[mat_id] = rescope

stats_op = ops.utility.statistical_fc()
stats_op.inputs.fields_container.connect(damage_op.outputs.damage_container)

final_merge = ops.utility.merge_fields()
final_merge.inputs.fields1.connect(threshold_op.outputs.boolean)
final_merge.inputs.fields2.connect(stats_op.outputs.field)

enhance_op = ops.mesh.nodal_to_elemental_fc()
enhance_op.inputs.fields_container.connect(final_merge.outputs.merged_fields)

output_connector = ops.utility.forward()
output_connector.inputs.any.connect(enhance_op.outputs.fields_container)

# ==================================================================
# Workflow Execution and Validation
# ==================================================================
workflow = dpf.Workflow()
workflow.add_operators([
    temp_op, grad_op, split_mat, damage_op, threshold_op,
    stats_op, final_merge, enhance_op, output_connector
])

workflow.set_input_name("time_scoping", temp_op.inputs.time_scoping)
workflow.set_output_name("damage_fields", output_connector.outputs.any)
workflow.set_output_name("critical_regions", threshold_op.outputs.boolean)

# Execute workflow
results = workflow.get_outputs()