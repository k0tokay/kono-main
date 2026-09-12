// src/store/PageContext.jsx
import React, { createContext, useReducer, useContext } from 'react';

const PageStateCtx = createContext();
const PageDispatchCtx = createContext();

const initialState = {
    leftWidth: 50,
    pageTabs: {
        left: {
            display: ['単語'],
            active: '単語'
        },
        right: {
            display: ['詳細', '検索'],
            active: '詳細'
        }
    }
};

function pageReducer(state, action) {
    switch (action.type) {
        case 'SET_TAB': {
            const { side, tab } = action.payload;
            return {
                ...state,
                pageTabs: {
                    ...state.pageTabs,
                    [side]: {
                        ...state.pageTabs[side],
                        active: tab
                    }
                }
            };
        }
        case 'OPEN_TAB': {
            const { side, tab } = action.payload;
            const exists = state.pageTabs[side].display.includes(tab);
            return {
                ...state,
                pageTabs: {
                    ...state.pageTabs,
                    [side]: {
                        display: exists
                            ? state.pageTabs[side].display
                            : [...state.pageTabs[side].display, tab],
                        active: tab
                    }
                }
            };
        }
        case 'SET_LEFT_WIDTH': {
            return { ...state, leftWidth: action.payload };
        }
        default:
            return state;
    }
}

export function PageProvider({ children }) {
    const [state, dispatch] = useReducer(pageReducer, initialState);
    return (
        <PageStateCtx.Provider value={state}>
            <PageDispatchCtx.Provider value={dispatch}>
                {children}
            </PageDispatchCtx.Provider>
        </PageStateCtx.Provider>
    );
}

export const usePageState = () => useContext(PageStateCtx);
export const usePageDispatch = () => useContext(PageDispatchCtx);
