import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadBlob, filenameFromContentDisposition } from "./download";

afterEach(() => vi.unstubAllGlobals());

describe("filenameFromContentDisposition", () => {
  it("использует filename из Content-Disposition и fallback при его отсутствии", () => {
    expect(filenameFromContentDisposition('attachment; filename="vacancies-2026-10-31.xlsx"', "fallback.xlsx")).toBe("vacancies-2026-10-31.xlsx");
    expect(filenameFromContentDisposition(null, "fallback.xlsx")).toBe("fallback.xlsx");
  });

  it("поддерживает UTF-8 filename*", () => {
    expect(filenameFromContentDisposition("attachment; filename*=UTF-8''%D0%B2%D0%B0%D0%BA%D0%B0%D0%BD%D1%81%D0%B8%D0%B8.xlsx", "fallback.xlsx")).toBe("вакансии.xlsx");
  });
});

describe("downloadBlob", () => {
  it("создаёт и освобождает browser object URL", () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:test");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadBlob(new Blob(["данные"]), "export.csv");

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
    click.mockRestore();
  });
});
