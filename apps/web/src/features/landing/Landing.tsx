import { Link } from 'react-router'
import { copy } from '@/lib/copy'
import { useAuth } from '@/lib/auth'

const features = [
  'Speak or type a note after a meeting and Gravv turns it into facts to remember, follow-ups, and the people who were mentioned, for you to confirm.',
  'Every relationship carries a Gravity score built from recency, frequency, tone, reciprocity, and depth, so you can see who is drifting before it costs you.',
  'Your personal contacts stay yours. Share a contact into your organization when you choose, and copy your own work back out at any time.',
]

export function Landing() {
  const { session } = useAuth()
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12 md:py-20">
      <p className="font-display text-xl font-bold text-steel-100">{copy.appName}</p>
      <h1 className="mt-8 max-w-prose font-display text-4xl font-bold text-steel-100">
        Know the gravity of your network
      </h1>
      <p className="mt-4 max-w-prose text-base text-steel-300">
        Gravv is a relationship operating system for people whose work depends on relationships that
        take months or years to build: sales, program management, diplomacy, consulting. It keeps
        the essence of each contact, the history of the relationship, and the context of the next
        conversation in one place.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        {session ? (
          <Link
            to="/app"
            className="chamfer-br inline-flex h-11 items-center bg-temper-500 px-5 text-sm font-medium text-steel-950"
          >
            Open Gravv
          </Link>
        ) : (
          <Link
            to="/auth/sign-up"
            className="chamfer-br inline-flex h-11 items-center bg-temper-500 px-5 text-sm font-medium text-steel-950"
          >
            Start free
          </Link>
        )}
        <a
          href="#how"
          className="inline-flex h-11 items-center bg-steel-700 px-5 text-sm font-medium text-steel-100 shadow-plate"
        >
          See how it works
        </a>
        {!session && (
          <Link
            to="/auth/sign-in"
            className="inline-flex h-11 items-center px-3 text-sm text-steel-300 hover:text-steel-100"
          >
            Sign in
          </Link>
        )}
      </div>
      <figure className="mt-12 border border-steel-600 bg-steel-800 p-2 shadow-plate">
        <img
          src="/screenshot-home.png"
          alt="The Gravv home screen: a stat row, contacts due next, recent activity, and insights."
          width={1280}
          height={800}
          className="block h-auto w-full"
          loading="eager"
        />
      </figure>
      <section id="how" className="mt-12 flex max-w-prose flex-col gap-4">
        <h2 className="font-display text-2xl font-bold text-steel-100">How it works</h2>
        {features.map((f) => (
          <p key={f} className="text-base text-steel-300">
            {f}
          </p>
        ))}
      </section>
      <footer className="mt-16 text-sm text-steel-400">
        Gravv runs on your data, under row-level security, with AI output treated as a proposal
        until you confirm it.
      </footer>
    </main>
  )
}
