export class PipelineFailure extends Error {
  constructor(code, { retryable = false, httpStatus = 500 } = {}) {
    super(code);
    this.name = 'PipelineFailure';
    this.code = code;
    this.retryable = retryable;
    this.httpStatus = httpStatus;
  }
}

export function failure(code, options) {
  return new PipelineFailure(code, options);
}
