from dataclasses import dataclass


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    description_en: str
    layer: str
    input: str
    output: str
    implementation: str

    def as_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "description_en": self.description_en,
            "layer": self.layer,
            "input": self.input,
            "output": self.output,
            "implementation": self.implementation,
        }
