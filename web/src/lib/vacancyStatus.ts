import type { VacancyStatus } from "../types/api";

export const vacancyStatusLabels: Record<VacancyStatus, string> = {
  active: "Активна",
  archived: "В архиве",
  closed: "Закрыта"
};
