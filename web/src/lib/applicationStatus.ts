import type { ApplicationStatus } from "../types/api";

export const applicationStatusLabels: Record<ApplicationStatus, string> = {
  submitted: "Отклик отправлен",
  response_received: "Ответ получен",
  screening: "Скрининг",
  test_task: "Тестовое",
  interview: "Интервью",
  offer: "Оффер",
  rejected: "Отказ",
  withdrawn: "Сам отказался"
};
