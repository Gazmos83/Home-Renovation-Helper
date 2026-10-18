# Rendering and presentation

## Materials and construction

Use the specification's material identity and grain direction. Prefer cached or supplied PBR textures; fetch suitable licensed assets when needed, recording source and physical texture scale. Poly Haven is optional. A suitable procedural material is an available fallback; disclose material mismatches without requiring a specific asset service.

Align UVs or local-coordinate mapping to each part's grain and use consistent real-world scale. Distinguish solid-wood end grain, plywood edges and veneer/banding. Use albedo with its intended color space; roughness, normal and height maps are non-color data. Feed normals through a Normal Map node. Start with textures sufficient for the final camera distance, increasing resolution only for visible improvement.

Use plausible roughness variation and restrained surface relief. New joinery does not automatically need wear, dirt or warped boards. Cosmetic effects must not alter fabrication geometry or measurements. Keep intentional construction gaps and edge treatments faithful to the specification.

## Fixtures and illumination

Separate fixture materials and moving/replaceable parts as needed. Position light sources at the physical emitter and preserve their alignment when parenting. Match emission size, direction, power and color temperature to the intended fixture.

For EEVEE, use appropriate Point/Spot/Area lights for reliable illumination, with visible bulb/shade materials and the required indirect-light/reflection setup. Configure supported light properties; Cycles light-node recipes are not portable to EEVEE.

Cycles emissive surfaces can illuminate a scene. If adding an explicit light to a glowing bulb, control the two contributions together rather than doubling the intended output. Drive bulb appearance and cast light from the same temperature. Blender light power is not a consumer bulb's electrical wattage or watt-equivalent rating.

Use an available IES profile only with verified engine support and correct orientation/intensity. Otherwise shape an explicit light and identify the distribution as approximate. Clear glass needs thickness and appropriate transmission; opal glass/fabric needs diffusion or scattering, not roughness alone. Metallic shading belongs to exposed metal, with directional roughness for brushed finishes. Check completed shader outputs, shadows and actual rendered illumination.

Keep flicker optional; if requested, couple light and visible emitter. Freeze lighting and procedural variation for a camera-only turntable.

## Quality and frame output

EEVEE is the app default. Cycles may be used for operator final renders when justified by the scene. Verify version-specific settings instead of copying old APIs. Inspect one inexpensive render and relevant detail crops before spending on final resolution/samples. Lock exposure, view transform and white balance; use denoising where appropriate and inspect whether it erases fine detail.

Frame cameras from actual object/room bounds. An interior orbit must avoid walls and clipped subjects; use suitable fixed views when an orbit cannot show the design. Render frame sequences only when requested, using one deterministic loop with a fixed seed and consistent settings.

Reuse [reference/viewer.html](../../../../reference/viewer.html) as an optional viewer starting point. Replace its demo title, dimensions and metadata for the intended audience. Match image paths, zero-padding and frame count to generated PNGs; exclude the duplicate full-revolution frame and verify every frame loads. Do not recreate the HTML inline on each task.

Engine details: [light shader support](https://docs.blender.org/manual/en/latest/render/shader_nodes/output/light.html), [emission](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/emission.html), [power units](https://docs.blender.org/manual/en/4.1/render/lights/light_object.html#power-of-lights).
