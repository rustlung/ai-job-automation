import { Link } from "react-router-dom";

export function NotFoundPage() { return <div className="grid min-h-[55vh] place-items-center text-center"><div><p className="text-sm text-zinc-500">404</p><h1 className="mt-2 text-2xl font-semibold">Страница не найдена</h1><Link className="mt-5 inline-block bg-zinc-900 px-4 py-2 text-sm font-medium text-white" to="/">На Dashboard</Link></div></div>; }
