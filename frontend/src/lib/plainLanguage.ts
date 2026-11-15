/**
 * End users should never see infrastructure names. Static copy is written in plain language
 * directly; this covers English text that arrives from the backend.
 */

const REPLACEMENTS: [RegExp, string][] = [
  [/Amazon Bedrock|Bedrock/g, "the AI model"],
  [/AWS Lambda|Lambda/g, "the calculation engine"],
  [/Amazon S3|\bS3\b/g, "the data store"],
  [/\bAWS\b/g, "the cloud"],
];

/** Replace infrastructure names in backend-written text with plain words. */
export function plain(text: string): string {
  return REPLACEMENTS.reduce((result, [pattern, replacement]) => result.replace(pattern, replacement), text);
}
