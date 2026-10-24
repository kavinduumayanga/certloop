export const DEFAULT_EMAIL_SUBJECT = "Your Certificate of Participation";

export const DEFAULT_EMAIL_BODY = `Hi {name},

Thank you for participating in our event!

We appreciate your time, enthusiasm, and involvement. Please find your personalized certificate of participation attached to this email.

We hope you enjoyed the experience and look forward to seeing you at our future events.

Best regards,
Event Organizing Team`;

const NAME_PLACEHOLDER =
  /{{\s*name\s*}}|(?<!{){\s*name\s*}(?!})/g;

export function renderEmailTemplate(template: string, name: string) {
  return template.replace(NAME_PLACEHOLDER, name);
}
