export function VacancyDescription({ description }: { description: string }) {
  const paragraphs = description.split(/\n\s*\n/).filter(Boolean);

  return <section className="border border-line bg-white p-5"><h2 className="text-lg font-semibold">Описание вакансии</h2><div className="mt-4 space-y-4 leading-7 text-zinc-700">{paragraphs.map((paragraph, index) => <p key={index} className="whitespace-pre-wrap">{paragraph}</p>)}</div></section>;
}
