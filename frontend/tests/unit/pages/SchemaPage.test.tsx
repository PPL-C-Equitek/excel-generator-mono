import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SchemaPage from '../../../src/app/schema/SchemaPage'

vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu, username }: { activeMenu: string; username: string }) => (
        <div data-testid="sidebar">
            <div data-testid="active-menu">{activeMenu}</div>
            <div data-testid="username">{username}</div>
        </div>
    ),
}))

vi.mock('../../../src/components/CustomSchemaManager', () => ({
    default: () => <div data-testid="custom-schema-manager">CustomSchemaManager</div>,
}))

describe('SchemaPage', () => {
    it('renders the schema builder heading and manager', () => {
        render(<SchemaPage />)

        expect(screen.getByText('Manage Your Custom Schemas')).toBeInTheDocument()
        expect(screen.getByTestId('custom-schema-manager')).toBeInTheDocument()
    })

    it('marks the schema menu as active in the sidebar', () => {
        render(<SchemaPage />)

        expect(screen.getByTestId('active-menu')).toHaveTextContent('schema')
        expect(screen.getByTestId('username')).toHaveTextContent('Username')
    })
})
