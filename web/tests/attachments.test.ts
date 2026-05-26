import { describe, expect, it } from "vitest";

import { attachmentUrl, staffAttachmentUrl } from "../src/api/attachments";

describe("attachmentUrl", () => {
  it("builds user view url", () => {
    expect(attachmentUrl(12, 5)).toBe("/api/v1/conversations/12/attachments/5");
  });
  it("builds staff view url", () => {
    expect(staffAttachmentUrl(12, 5)).toBe("/staff/api/v1/conversations/12/attachments/5");
  });
});
