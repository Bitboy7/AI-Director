def fragment_prompt(fragment) -> str:
    """Prompt de video del fragmento: une los prompts de los paneles del storyboard.

    Si no hay storyboard, usa el prompt del fragmento (prompt_video).
    """
    panels = [
        panel.prompt.strip()
        for panel in fragment.storyboard
        if panel.prompt and panel.prompt.strip()
    ]
    if panels:
        return " ".join(panels)
    return fragment.prompt_video or f"Plano {fragment.shot_number}"
