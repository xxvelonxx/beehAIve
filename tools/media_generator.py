class MediaGenerator:
    def generate_image_prompt(self, objective: str) -> str:
        return (
            f"A professional, high-quality photo of: {objective}. "
            "Hyper-realistic, cinematic lighting, ultra-detailed, 8K resolution, "
            "photorealistic rendering, award-winning photography."
        )

    def generate_video_plan(self, objective: str) -> dict:
        return {
            "concept": f"Cinematic video showcasing: {objective}",
            "scenes": [
                f"Scene 1: Wide establishing shot — {objective}",
                f"Scene 2: Close-up detail — key features of {objective}",
                f"Scene 3: Dynamic action or interaction with {objective}",
                f"Scene 4: Emotional reveal or testimonial moment",
                f"Scene 5: Strong closing shot with branding",
            ],
            "style": "Modern, dynamic, professional production. Think Apple-level quality.",
            "duration": "60-90 seconds recommended",
            "tools": ["Sora", "Runway Gen-3", "Kling", "Pika"],
        }

    def generate_audio_script(self, objective: str) -> str:
        return (
            f"Professional voice-over script for: {objective}.\n"
            "Tone: Confident, inspiring, clear.\n"
            "Keep it under 30 seconds. End with a strong call to action."
        )


media_generator = MediaGenerator()
