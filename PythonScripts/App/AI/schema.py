AI_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "job_match_evaluation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "temp_id": {"type": "integer"},
                            "detected_role": {"type": "string"},
                            "detected_level": {
                                "type": "string",
                                "enum": [
                                    "Trainee",
                                    "Intern",
                                    "Junior",
                                    "Middle",
                                    "Senior",
                                    "Lead",
                                    "Unknown",
                                ],
                            },
                            "role_match": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "level_match": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "tech_match": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "experience_match": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "critical_mismatch": {"type": "boolean"},
                            "critical_reason": {"type": "string"},
                            "TechStack": {"type": "string"},
                            "AiSummary": {"type": "string"},
                            "ExtractedExperience": {"type": "string"},
                        },
                        "required": [
                            "temp_id",
                            "detected_role",
                            "detected_level",
                            "role_match",
                            "level_match",
                            "tech_match",
                            "experience_match",
                            "critical_mismatch",
                            "critical_reason",
                            "TechStack",
                            "AiSummary",
                            "ExtractedExperience",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["results"],
            "additionalProperties": False,
        },
    },
}
