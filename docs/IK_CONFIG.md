# IK Config

In our IK config such as `smplx_to_g1.json`, you might find following params. I add annotations here for your understanding.

```json
"ik_match_table1": {
        "pelvis": [ # robot's body name
            "pelvis", # corresponding human body name, here we are using "pelvis" as example
            100, # weight to track 3D positions (xyz)
            10, # weight to track 3D rotations
            [
                0.0, # x offset added to human body "pelvis" x
                0.0, # y offset added to human body "pelvis" y
                0.0 # z offset added to human body "pelvis" z
            ],
            [
                # the rotation (represented as quaternion) applied to human body "pelvis". the order follows scalar first (wxyz)
                0.5,
                -0.5,
                -0.5,
                -0.5
            ]
        ],
      ...
```
