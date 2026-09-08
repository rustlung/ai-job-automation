import { Link, useParams } from "react-router-dom";

export function VacancyDetailPlaceholderPage() {
  const { presentationKey } = useParams();
  return <div className="grid min-h-[55vh] place-items-center text-center"><div><p className="text-sm text-zinc-500">{presentationKey ?? "Vacancy"}</p><h1 className="mt-2 text-2xl font-semibold">Vacancy Detail</h1><p className="mt-3 text-zinc-600">Карточка вакансии будет добавлена следующим milestone.</p><Link className="mt-5 inline-block bg-zinc-900 px-4 py-2 text-sm font-medium text-white" to="/vacancies">К списку вакансий</Link></div></div>;
}
