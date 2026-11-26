def serialize_category(category):
    return {"slug": category.slug, "name": category.name}


def serialize_opposition_summary(opposition):
    return {
        "slug": opposition.slug,
        "name": opposition.name,
        "category": serialize_category(opposition.category),
        "icon": opposition.icon,
        "color": opposition.color,
        "questionCount": opposition.question_count,
    }


def serialize_opposition_detail(opposition):
    presets = list(opposition.practice_presets.all())
    return {
        **serialize_opposition_summary(opposition),
        "description": opposition.description,
        "topics": [
            {
                "slug": topic.slug,
                "name": topic.name,
                "questionCount": topic.question_count,
                "concepts": topic.concepts,
            }
            for topic in opposition.topics.all()
        ],
        "practice": {
            "easy": _serialize_single_preset(presets, "easy"),
            "difficult": _serialize_single_preset(presets, "difficult"),
            "fullMocks": [
                {
                    "id": preset.mock_id,
                    "number": preset.mock_number,
                    "questionCount": preset.question_count,
                    "durationMinutes": preset.duration_minutes,
                }
                for preset in presets
                if preset.mode == "full"
            ],
        },
        "contentReviewedAt": None,
    }


def _serialize_single_preset(presets, mode):
    preset = next((item for item in presets if item.mode == mode), None)
    if preset is None:
        return None
    return {
        "questionCount": preset.question_count,
        "durationMinutes": preset.duration_minutes,
    }
