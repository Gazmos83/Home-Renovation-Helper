/** How each specialist is named to the owner: by role only, never by model. */
export const ROLE_LABELS: Record<string, string> = {
  foreman: "Foreman",
  intake: "Intake",
  designer: "Designer",
  builder: "Builder",
  lighting: "Lighting & materials",
  reviewer: "Reviewer",
  researcher: "Researcher",
};

/** How each speaker is named on the homeowner's screens (meet-the-crew); developer views keep `ROLE_LABELS`. */
export const PERSONA_NAMES: Record<string, string> = {
  foreman: "Little Homey",
  intake: "Lil' Worm",
  designer: "Lil' Glitty",
  builder: "Muscles",
  lighting: "Bulbs",
  reviewer: "Mr. Lookback",
  researcher: "Money Bags",
  engineering: "Little Beam",
};

/** A speaker's persona; a reply with no or an unknown speaker is Little Homey's. */
export function personaOf(speaker?: string | null): string {
  return (speaker && PERSONA_NAMES[speaker]) || PERSONA_NAMES.foreman;
}
