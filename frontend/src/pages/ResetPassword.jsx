import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function ResetPassword() {
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, new_password: newPassword }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Reset failed')
        return
      }

      setSuccess('Password updated! Redirecting to sign in...')
      setTimeout(() => navigate('/login'), 2000)
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
          Set new password
        </h1>
        <p className="text-sm text-gray-500 text-center mb-8">
          Enter the reset code from your email and your new password.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 rounded-lg bg-green-50 text-green-700 text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="code" className="block text-sm font-medium text-gray-700 mb-1">
              Reset code
            </label>
            <input
              id="code"
              type="text"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Paste the code from your email"
            />
          </div>

          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 mb-1">
              New password
            </label>
            <input
              id="new-password"
              type="password"
              required
              minLength={8}
              maxLength={128}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Min 8 characters"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Resetting...' : 'Reset password'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          <Link to="/login" className="text-blue-600 hover:text-blue-700 font-medium">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
