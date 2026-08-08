const correlationIdPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/;

export function isValidCorrelationId(value: string): boolean {
  return correlationIdPattern.test(value);
}
