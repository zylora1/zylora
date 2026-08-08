import { z } from 'zod';

export const publicWebConfigSchema = z.object({
  NEXT_PUBLIC_API_URL: z.url(),
});

export type PublicWebConfig = z.infer<typeof publicWebConfigSchema>;

export function parsePublicWebConfig(input: unknown): PublicWebConfig {
  return publicWebConfigSchema.parse(input);
}
