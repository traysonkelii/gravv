import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

const control =
  'w-full bg-steel-900 text-steel-100 placeholder:text-steel-500 border border-steel-600 border-b-2 border-b-steel-500 ' +
  'px-3 h-11 md:h-10 text-base focus:border-b-temper-500 focus:outline-none focus-visible:outline-2 ' +
  'disabled:text-steel-500 aria-invalid:border-b-rust-500'

type Wrap = {
  label: string
  hint?: string
  error?: string
  children: ReactNode
  id: string
  className?: string
}

function Wrap({ label, hint, error, children, id, className = '' }: Wrap) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="text-sm text-steel-300">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-rust-400">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-sm text-steel-400">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, id, className = '', ...rest },
  ref,
) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Wrap label={label} hint={hint} error={error} id={fieldId} className={className}>
      <input
        ref={ref}
        id={fieldId}
        className={control}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        {...rest}
      />
    </Wrap>
  )
})

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string
  hint?: string
  error?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, id, className = '', rows = 4, ...rest },
  ref,
) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Wrap label={label} hint={hint} error={error} id={fieldId} className={className}>
      <textarea
        ref={ref}
        id={fieldId}
        rows={rows}
        className={`${control} h-auto py-2 leading-6`}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        {...rest}
      />
    </Wrap>
  )
})

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  hint?: string
  error?: string
  children: ReactNode
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, id, className = '', children, ...rest },
  ref,
) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Wrap label={label} hint={hint} error={error} id={fieldId} className={className}>
      <select
        ref={ref}
        id={fieldId}
        className={control}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        {...rest}
      >
        {children}
      </select>
    </Wrap>
  )
})
